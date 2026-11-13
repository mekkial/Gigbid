import os
import uuid

os.environ["DATABASE_URL"] = "postgresql://gigbid@localhost:5433/gigbid_test"
os.environ["GIGBID_TOOLS"] = "local"
os.environ["GIGBID_QUEUE"] = "inline"
os.environ.pop("REDIS_URL", None)

import asyncio

import httpx
import pytest_asyncio
from langgraph.checkpoint.memory import MemorySaver

from apps.api import queue
from apps.api.main import app
from apps.api.runtime import RUNTIME
from gigsim import app as g
from tests.integration.conftest import offline_impl

g.RULES["error_rate_5xx"] = 0.0
g.RULES["rate_limit_per_minute"] = 100000
g.RULES["connects"]["starting_balance"] = 10_000_000


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def runtime():
    from apps.api import db
    await RUNTIME.start()
    RUNTIME.checkpointer = MemorySaver()                  # test isolation; durability is covered by the crash-resume test
    RUNTIME.impl = offline_impl()
    # route LocalToolbox's GigSim adapter through the in-process ASGI app
    from mcp_servers.marketplace.adapters import gigsim as ga
    orig = ga.GigSimAdapter.__init__
    def patched(self, *a, **k):
        k.setdefault("client", httpx.AsyncClient(transport=httpx.ASGITransport(app=g.app), base_url="http://t")); orig(self, *a, **k)
    ga.GigSimAdapter.__init__ = patched
    await queue.init()
    yield RUNTIME
    ga.GigSimAdapter.__init__ = orig
    await db.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(runtime):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as c:
        yield c


async def signup(client, persona="ai_ml"):
    email = f"{uuid.uuid4().hex[:8]}@test.dev"
    r = await client.post("/api/auth/register", json={"email": email, "password": "password123", "persona": persona})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def wait_status(client, headers, statuses, timeout=60, job=None):
    for _ in range(int(timeout / 0.3)):
        rows = (await client.get("/api/jobs", headers=headers)).json()
        hit = [r for r in rows if r["status"] in statuses and (job is None or r["job_id"] == job)]
        if hit:
            return hit
        await asyncio.sleep(0.3)
    raise AssertionError(f"timeout waiting for {statuses}: {(await client.get('/api/jobs', headers=headers)).json()}")
