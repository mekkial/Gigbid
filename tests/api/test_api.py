import asyncio

import pytest

from tests.api.conftest import signup, wait_status
from tests.integration.conftest import dev_jobs

pytestmark = pytest.mark.asyncio(loop_scope="session")
JOBS = dev_jobs()
GOOD = [j for j in JOBS if j["gold"]["decision"] == "bid" and not j["gold"]["injected"] and "duplicate_of" not in j]
SCAM = next(j for j in JOBS if j["gold"]["scam"] and "duplicate_of" not in j)


async def test_requires_auth(client):
    assert (await client.get("/api/jobs")).status_code == 401
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer junk"})).status_code == 401


async def test_register_login_me_and_settings(client):
    h = await signup(client, "fullstack")
    me = (await client.get("/api/auth/me", headers=h)).json()
    assert me["persona"] == "fullstack" and me["settings"]["autonomy"] == "manual"
    r = await client.put("/api/settings", headers=h, json={"settings": {"floor_hourly": 45, "autonomy": "auto_skip_low_fit"}})
    assert r.json()["settings"]["floor_hourly"] == 45
    bad = await client.put("/api/settings", headers=h, json={"settings": {"floor_hourly": -5}})
    assert bad.status_code == 422


async def test_full_journey_scam_skipped_and_proposal_approved_once(client):
    h = await signup(client)
    for j in (SCAM, GOOD[0]):
        assert (await client.post(f"/api/jobs/{j['job_id']}/analyse", headers=h)).json()["created"] is True
    skipped = await wait_status(client, h, {"skipped"}, job=SCAM["job_id"])
    assert skipped[0]["decision"] == "skip"
    waiting = (await wait_status(client, h, {"awaiting_approval"}, job=GOOD[0]["job_id"]))[0]
    tid = waiting["thread_id"]
    # approval payload carries draft, evidence, risk, price, dry-run (C5)
    p = (await client.get(f"/api/approvals/{tid}", headers=h)).json()
    assert {"draft", "evidence", "risk_report", "price_quote", "dry_run", "claims"} <= set(p) and p["dry_run"]["dry_run"] is True
    # pending approval survives a "page refresh": still listed
    assert tid in [a["thread_id"] for a in (await client.get("/api/approvals", headers=h)).json()]
    # approve twice concurrently: exactly one is accepted
    r = await asyncio.gather(*[client.post(f"/api/approvals/{tid}", headers=h, json={"action": "approve"}) for _ in range(2)])
    assert sorted(x.status_code for x in r) == [200, 409]
    sub = (await wait_status(client, h, {"submitted"}, job=GOOD[0]["job_id"]))[0]
    assert sub["proposal_id"]
    pipe = (await client.get("/api/pipeline", headers=h)).json()
    assert any(c["thread_id"] == tid and c["stage"] in ("submitted", "viewed", "replied", "interview", "hired", "lost") for c in pipe)


async def test_reject_requires_reason_and_is_counted(client):
    h = await signup(client)
    await client.post(f"/api/jobs/{GOOD[1]['job_id']}/analyse", headers=h)
    tid = (await wait_status(client, h, {"awaiting_approval"}, job=GOOD[1]["job_id"]))[0]["thread_id"]
    assert (await client.post(f"/api/approvals/{tid}", headers=h, json={"action": "reject"})).status_code == 422
    assert (await client.post(f"/api/approvals/{tid}", headers=h, json={"action": "reject", "reason": "too generic"})).status_code == 200
    await wait_status(client, h, {"rejected"}, job=GOOD[1]["job_id"])
    an = (await client.get("/api/analytics", headers=h)).json()
    assert {"reason": "too generic", "n": 1} in an["rejection_reasons"]


async def test_tenant_isolation(client):
    a, b = await signup(client), await signup(client)
    await client.post(f"/api/jobs/{GOOD[2]['job_id']}/analyse", headers=a)
    tid = (await wait_status(client, a, {"awaiting_approval"}, job=GOOD[2]["job_id"]))[0]["thread_id"]
    assert (await client.get("/api/jobs", headers=b)).json() == []
    assert (await client.get(f"/api/approvals/{tid}", headers=b)).status_code == 404
    assert (await client.post(f"/api/approvals/{tid}", headers=b, json={"action": "approve"})).status_code == 409
    assert (await client.get(f"/api/runs/{tid}", headers=b)).status_code == 404


async def test_duplicate_repost_not_reanalysed(client):
    h = await signup(client)
    j = GOOD[3]
    dup = next((d for d in JOBS if d.get("duplicate_of") == j["job_id"]), None)
    assert (await client.post(f"/api/jobs/{j['job_id']}/analyse", headers=h)).json()["created"] is True
    assert (await client.post(f"/api/jobs/{j['job_id']}/analyse", headers=h)).json()["created"] is False     # same job: idempotent
    if dup:
        assert (await client.post(f"/api/jobs/{dup['job_id']}/analyse", headers=h)).json()["created"] is False  # same content: deduped


async def test_edit_feeds_style_memory_visible_and_deletable(client):
    h = await signup(client)
    for k in range(3):
        j = GOOD[4 + k]
        await client.post(f"/api/jobs/{j['job_id']}/analyse", headers=h)
        w = (await wait_status(client, h, {"awaiting_approval"}, job=j["job_id"]))[0]
        p = (await client.get(f"/api/approvals/{w['thread_id']}", headers=h)).json()
        edited = " ".join(p["send_text"].split(". ")[1:])
        await client.post(f"/api/approvals/{w['thread_id']}", headers=h, json={"action": "edit", "text": edited})
        await wait_status(client, h, {"submitted", "blocked"}, job=j["job_id"])
    mem = (await client.get("/api/memory", headers=h)).json()
    rule = next(m for m in mem if m["namespace"] == "style" and "first sentence" in m["value"]["rule"])
    assert (await client.delete(f"/api/memory/style/{rule['key']}", headers=h)).json()["deleted"]
    assert not any(m["key"] == rule["key"] for m in (await client.get("/api/memory", headers=h)).json())


async def test_run_stream_replays_trace(client):
    h = await signup(client)
    await client.post(f"/api/jobs/{GOOD[8]['job_id']}/analyse", headers=h)
    tid = (await wait_status(client, h, {"awaiting_approval"}, job=GOOD[8]["job_id"]))[0]["thread_id"]
    async with client.stream("GET", f"/api/runs/{tid}/stream", headers=h) as r:
        body = ""
        async for line in r.aiter_lines():
            body += line + "\n"
            if "awaiting_approval" in line:
                break
    assert "analyst" in body and "fit_matcher" in body and "awaiting_approval" in body
    hist = (await client.get(f"/api/runs/{tid}/history", headers=h)).json()
    assert len(hist) > 5 and all("checkpoint_id" in x for x in hist)


async def test_degraded_banner_source_reports_marketplace_down(client):
    from gigsim import app as g
    h = await signup(client)
    assert (await client.get("/api/health/tools", headers=h)).json()["marketplace"] == "up"
    g.FAIL_NEXT["n"] = 50
    try:
        assert (await client.get("/api/health/tools", headers=h)).json()["marketplace"] == "down"
    finally:
        g.FAIL_NEXT["n"] = 0
