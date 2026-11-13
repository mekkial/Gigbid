"""Live adapter + OAuth, tested against a FAKE Upwork-style MCP server and mocked OAuth endpoints (no Upwork account needed)."""
import asyncio
import contextlib
import json
import sys
import textwrap

import httpx
import pytest

from agent.marketplace_port import get_marketplace
from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter

FAKE_SERVER = textwrap.dedent('''
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("fake-upwork")
    @mcp.tool()
    def search_jobs_by_query(query: str, limit: int = 20) -> list[dict]:
        return [{"job_id": "up-1", "title": f"Result for {query}", "description": "d", "required_skills": ["Python"], "budget": {"min": 1, "max": 2}, "client_id": "c1", "connects_cost": 8}]
    @mcp.tool()
    def get_job_details(job_id: str) -> dict:
        return {"job_id": job_id, "title": "A job"}
    @mcp.tool()
    def get_connects_balance_info() -> dict:
        return {"balance": 42}
    @mcp.tool()
    def create_proposal_draft_for_job(job_id: str, cover_letter: str, bid_amount: float, idempotency_key: str) -> dict:
        return {"proposal_id": "draft-1", "status": "draft"}
    mcp.run()
''')


@pytest.fixture
def adapter(tmp_path):
    f = tmp_path / "fake_upwork.py"; f.write_text(FAKE_SERVER)
    return UpworkLiveAdapter(connection={"transport": "stdio", "command": sys.executable, "args": [str(f)]}, min_interval_s=0)


async def test_tools_are_discovered_by_keyword_and_mapped_onto_the_port(adapter):
    assert (await adapter.search_jobs("rag", 5))[0]["job_id"] == "up-1"
    assert (await adapter.get_job("up-1"))["title"] == "A job"
    assert (await adapter.get_connects_balance())["balance"] == 42
    assert adapter._tools["search_jobs"] == "search_jobs_by_query" and adapter._tools["get_job"] == "get_job_details"


async def test_live_mode_never_submits_and_only_creates_drafts(adapter):
    d = await adapter.create_proposal_draft({"job_id": "up-1", "cover_letter": "x" * 200, "bid_amount": 10}, "idem-key-1")
    assert d["draft_only"] is True and d["status"] == "draft"
    sub = await adapter.submit_proposal("draft-1", "idem-key-2")
    assert sub["status"] == "draft_pending_user_confirmation" and sub["outcome"] is None       # the user confirms on Upwork


async def test_dry_run_calls_nothing_and_missing_tool_is_explicit(adapter):
    p = await adapter.create_proposal_draft({"job_id": "j"}, "k" * 8, dry_run=True)
    assert p["dry_run"] is True and adapter._tools is None                                      # no connection was even made
    with pytest.raises(NotImplementedError):
        await adapter.list_messages("x")                                                        # fake server has no message tool


async def test_not_connected_is_reported_as_unavailable():
    from agent.marketplace_port import MarketplaceUnavailable
    with pytest.raises(MarketplaceUnavailable, match="not connected"):
        await UpworkLiveAdapter(min_interval_s=0).get_connects_balance()


def test_factory_switches_adapter_by_config_only():
    from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
    assert isinstance(get_marketplace("gigsim"), GigSimAdapter)
    assert isinstance(get_marketplace("upwork_live"), UpworkLiveAdapter)


async def test_oauth_discovery_registration_and_pkce(monkeypatch):
    from apps.api.routers import upwork_oauth as o
    def handler(req: httpx.Request):
        u = str(req.url)
        if u.endswith("/.well-known/oauth-protected-resource"):
            return httpx.Response(200, json={"authorization_servers": ["https://auth.example"]})
        if u.endswith("/.well-known/oauth-authorization-server"):
            return httpx.Response(200, json={"authorization_endpoint": "https://auth.example/authorize", "token_endpoint": "https://auth.example/token", "registration_endpoint": "https://auth.example/register"})
        if u.endswith("/register"):
            body = json.loads(req.content); assert body["token_endpoint_auth_method"] == "none" and body["redirect_uris"]
            return httpx.Response(200, json={"client_id": "cid-123"})
        return httpx.Response(404)
    monkeypatch.delenv("UPWORK_CLIENT_ID", raising=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        meta = await o.discover(http)
        assert await o.register_client(http, meta) == "cid-123"
    verifier, challenge = o.pkce()
    import base64, hashlib
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode() and len(verifier) >= 43


def test_live_mode_enforces_polite_polling_interval():
    from agent.llm import load_config
    assert load_config()["marketplace"]["live"]["min_poll_interval_min"] >= 180
