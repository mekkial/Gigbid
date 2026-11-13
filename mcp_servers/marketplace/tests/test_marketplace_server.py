import json
import sqlite3

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect
from starlette.testclient import TestClient

from gigsim import app as g
from mcp_servers import common
from mcp_servers.marketplace import server as srv
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

g.RULES["error_rate_5xx"] = 0.0
g.RULES["rate_limit_per_minute"] = 100000
LETTER = "I recently built a churn model for a fintech client and can do the same here. " * 4


@pytest.fixture(autouse=True)
def wire(monkeypatch):
    def adapter(user):
        return GigSimAdapter(user=user, client=httpx.AsyncClient(transport=httpx.ASGITransport(app=g.app), base_url="http://t"), backoff=0.01)
    monkeypatch.setattr(srv, "adapter_for", adapter)
    monkeypatch.setattr(srv, "LEDGER", common.Ledger(":memory:"))
    monkeypatch.setattr(srv, "LIMITER", common.RateLimiter(1000))


def sc(r):
    return r.structuredContent


async def first_job(c):
    r = await c.call_tool("search_jobs", {"limit": 1})
    return sc(r)["items"][0]


async def test_tool_annotations_and_schemas():
    async with connect(srv.mcp._mcp_server) as c:
        t = {x.name: x for x in (await c.list_tools()).tools}
        assert t["search_jobs"].annotations.readOnlyHint is True
        assert t["create_proposal_draft"].annotations.idempotentHint is True and not t["create_proposal_draft"].annotations.readOnlyHint
        assert t["submit_proposal"].annotations.destructiveHint is True
        assert all(t[w].outputSchema for w in ("create_proposal_draft", "submit_proposal", "send_message"))
        props = t["create_proposal_draft"].inputSchema["properties"]
        assert props["cover_letter"]["minLength"] == 150 and props["bid_amount"]["exclusiveMinimum"] == 0
        assert "idempotency_key" in t["create_proposal_draft"].inputSchema["required"]


async def test_invalid_inputs_rejected_by_schema():
    async with connect(srv.mcp._mcp_server) as c:
        j = await first_job(c)
        r = await c.call_tool("create_proposal_draft", {"job_id": j["job_id"], "cover_letter": "short", "bid_amount": 10, "idempotency_key": "k" * 10})
        assert r.isError
        r = await c.call_tool("create_proposal_draft", {"job_id": j["job_id"], "cover_letter": LETTER, "bid_amount": 10, "idempotency_key": "x"})
        assert r.isError


async def test_dry_run_previews_cost_without_writing():
    async with connect(srv.mcp._mcp_server) as c:
        j = await first_job(c)
        before = sc(await c.call_tool("get_connects_balance", {}))
        r = sc(await c.call_tool("create_proposal_draft", {"job_id": j["job_id"], "cover_letter": LETTER, "bid_amount": 100,
                                                          "idempotency_key": "dryrun-key-1", "dry_run": True}))
        assert r["dry_run"] and r["data"]["connects_cost"] == j["connects_cost"]
        assert sc(await c.call_tool("get_connects_balance", {})) == before


async def test_idempotent_submit_spends_connects_once():
    async with connect(srv.mcp._mcp_server) as c:
        j = await first_job(c)
        d = sc(await c.call_tool("create_proposal_draft", {"job_id": j["job_id"], "cover_letter": LETTER, "bid_amount": 120, "idempotency_key": "create-key-1"}))
        pid = d["data"]["proposal_id"]
        b0 = sc(await c.call_tool("get_connects_balance", {}))["balance"]
        a = sc(await c.call_tool("submit_proposal", {"proposal_id": pid, "idempotency_key": "submit-key-1"}))
        b = sc(await c.call_tool("submit_proposal", {"proposal_id": pid, "idempotency_key": "submit-key-1"}))
        assert a["replayed"] is False and b["replayed"] is True and a["data"] == b["data"]
        assert b0 - sc(await c.call_tool("get_connects_balance", {}))["balance"] == j["connects_cost"]


async def test_audit_log_append_only_and_pii_masked():
    async with connect(srv.mcp._mcp_server) as c:
        j = await first_job(c)
        await c.call_tool("create_proposal_draft", {"job_id": j["job_id"], "cover_letter": LETTER + " mail me at bob@example.com or +1 415 555 0100",
                                                    "bid_amount": 50, "idempotency_key": "audit-key-01", "dry_run": True})
    rows = srv.LEDGER.audit_rows()
    assert any(r[2] == "create_proposal_draft" for r in rows)
    blob = json.dumps(rows)
    assert "bob@example.com" not in blob and "415 555 0100" not in blob and "[email]" in blob
    with pytest.raises(sqlite3.DatabaseError):
        srv.LEDGER.db.execute("DELETE FROM audit")
    with pytest.raises(sqlite3.DatabaseError):
        srv.LEDGER.db.execute("UPDATE audit SET user='x'")


async def test_rate_limiter_blocks_bursts(monkeypatch):
    monkeypatch.setattr(srv, "LIMITER", common.RateLimiter(3))
    async with connect(srv.mcp._mcp_server) as c:
        res = [await c.call_tool("get_connects_balance", {}) for _ in range(5)]
    assert any(r.isError and "rate_limited" in r.content[0].text for r in res)


async def test_marketplace_down_reports_degraded_error(monkeypatch):
    async with connect(srv.mcp._mcp_server) as c:
        await c.call_tool("get_connects_balance", {})
        g.FAIL_NEXT["n"] = 50
        try:
            r = await c.call_tool("get_connects_balance", {})
        finally:
            g.FAIL_NEXT["n"] = 0
    assert r.isError and "marketplace_unavailable" in r.content[0].text


def test_http_requires_bearer_token():
    with TestClient(srv.http_app()) as cl:
        assert cl.post("/mcp", json={}).status_code == 401
        assert cl.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert cl.get("/health").status_code in (200, 401)
