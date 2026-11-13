"""Change request (simulated 2 Nov platform update): a new mandatory disclosure rule and a small-job Connects surcharge."""
import os

os.environ.setdefault("GIGSIM_API_TOKEN", "dev-token")
from fastapi.testclient import TestClient

from agent.nodes.compliance import check, strip_citations
from gigsim import app as g

BODY = "I recently delivered a churn model for a fintech client and would apply the same approach here. " * 3


def test_required_disclosure_is_appended_once_and_survives_edits():
    v = check(BODY)
    assert v.cleaned_text.endswith("reviewed by me.") and v.allowed
    again = check(v.cleaned_text)                                  # idempotent: a human edit that keeps it does not duplicate it
    assert again.cleaned_text.count("drafted with AI assistance") == 1
    assert "drafted with AI assistance" in check(strip_citations(BODY + " [evidence: x]")).cleaned_text


def test_surcharge_is_visible_to_gigbid_without_code_changes():
    g.RULES["error_rate_5xx"] = 0.0
    c = TestClient(g.app); H = {"Authorization": "Bearer dev-token", "x-user": "cr"}
    jobs = c.get("/jobs?limit=500", headers=H).json()["items"]
    small = next(j for j in jobs if 0 < j["budget"]["max"] < 500)
    assert small["connects_cost"] == g.JOBS[small["job_id"]]["connects_cost"] + 2
    big = next(j for j in jobs if j["budget"]["max"] >= 500)
    assert big["connects_cost"] == g.JOBS[big["job_id"]]["connects_cost"]
