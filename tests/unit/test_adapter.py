import httpx
import pytest

from gigsim import app as g
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

g.RULES["error_rate_5xx"] = 0.0


def make():
    transport = httpx.ASGITransport(app=g.app)
    client = httpx.AsyncClient(transport=transport, base_url="http://t")
    return GigSimAdapter(token="dev-token", user="adapter", client=client, backoff=0.01)


async def test_search_and_dry_run_does_not_spend():
    a = make()
    job = (await a.search_jobs("", 1))[0]
    before = (await a.get_connects_balance())["balance"]
    prev = await a.create_proposal_draft({"job_id": job["job_id"], "cover_letter": "x" * 200, "bid_amount": 100}, "k", dry_run=True)
    assert prev["dry_run"] and prev["connects_cost"] == job["connects_cost"]
    assert (await a.get_connects_balance())["balance"] == before


async def test_retries_through_transient_503():
    a = make()
    await a._client.post("/_admin/fail_next/2")
    assert "balance" in await a.get_connects_balance()
