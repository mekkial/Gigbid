from fastapi.testclient import TestClient

from gigsim import app as g

H = {"Authorization": "Bearer dev-token", "x-user": "t1"}
g.RULES["error_rate_5xx"] = 0.0
c = TestClient(g.app)


def _job():
    return c.get("/jobs?limit=1", headers=H).json()["items"][0]


def test_auth_required():
    assert c.get("/jobs").status_code == 401


def test_gold_and_prefs_hidden():
    j = _job()
    assert "gold" not in j
    cl = c.get(f"/clients/{j['client_id']}", headers=H).json()
    assert "prefs" not in cl


def test_submit_idempotent_and_spends_connects_once():
    j = _job()
    body = {"job_id": j["job_id"], "cover_letter": "I recently delivered " + j["required_skills"][0] * 1 + " work. " * 40,
            "bid_amount": 500}
    p = c.post("/proposals", json=body, headers={**H, "Idempotency-Key": "k1"}).json()
    before = c.get("/connects", headers=H).json()["balance"]
    r1 = c.post(f"/proposals/{p['proposal_id']}/submit", headers={**H, "Idempotency-Key": "s1"}).json()
    r2 = c.post(f"/proposals/{p['proposal_id']}/submit", headers={**H, "Idempotency-Key": "s1"}).json()
    after = c.get("/connects", headers=H).json()["balance"]
    assert r1["status"] == "submitted" and r1 == r2
    assert before - after == p["connects_cost"]


def test_rate_limit_and_outage():
    h = {**H, "x-user": "ratelimited"}
    codes = [c.get("/connects", headers=h).status_code for _ in range(g.RULES["rate_limit_per_minute"] + 2)]
    assert 429 in codes
    c.post("/_admin/fail_next/1")
    assert c.get("/connects", headers={**H, "x-user": "other"}).status_code == 503
