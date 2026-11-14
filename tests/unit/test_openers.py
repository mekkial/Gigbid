from agent.handoffs import ProposalDraft
from agent.nodes import critic
from agent.nodes.openers import copied_opening_words

JOB = {"title": "Need dbt data models", "description": "We are a marketing team looking for an expert to build dbt data models. Must know SQL."}


def test_copied_opening_detected():
    assert copied_opening_words("We are a marketing team looking for an expert to build dbt data models, and I have experience.", JOB["title"], JOB["description"]) >= 9


def test_own_words_pass():
    assert copied_opening_words("Reliable dbt models start with clean joins; I built that for a logistics client.", JOB["title"], JOB["description"]) < 6


def test_critic_rejects_copied_opening(monkeypatch):
    from agent.handoffs import Critique
    monkeypatch.setattr(critic, "chat_json", lambda *a, **k: Critique(approved=True, grounding=0.9, personalisation=0.8))
    body = ("We are a marketing team looking for an expert to build dbt data models, and I have experience. " + "I built warehouse models. " * 30)
    d = ProposalDraft(job_id="j1", cover_letter=body)
    c = critic.review(JOB, d, unsupported=0)
    assert not c.approved and any("repeats" in i for i in c.issues)
