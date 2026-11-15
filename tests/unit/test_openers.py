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


def test_compliance_keeps_interview_slots_but_strips_phone_numbers():
    from agent.nodes.compliance import check
    v = check("I can offer Mon 2026-11-16 10:00, Mon 2026-11-16 11:00 or Tue 2026-11-17 14:00. " + "Happy to discuss the project in detail and answer questions. " * 3)
    assert "2026-11-16 10:00" in v.cleaned_text and "off_platform_contact" not in v.violations
    w = check("Call me on +92 300 1234567 to discuss. " + "Happy to discuss the project in detail and answer questions. " * 3)
    assert "1234567" not in w.cleaned_text and "off_platform_contact" in w.violations


def test_bm25_mode_builds_no_embeddings_and_full_mode_default_is_v3(monkeypatch):
    import rag.retriever as r
    from rag.index.store import Index
    chunks = [{"chunk_id": "a", "text": "RAG chatbot with Hugging Face", "skills": ["rag"], "project": "p1", "type": "case_study"},
              {"chunk_id": "b", "text": "React dashboard", "skills": ["react"], "project": "p2", "type": "case_study"}]
    monkeypatch.setenv("RAG_VARIANT", "v6_bm25")
    idx = Index(chunks)
    assert idx.emb is None and r.active_variant() == "v6_bm25"
    assert r.get_retriever()("RAG chatbot", idx, k=1)[0]["project"] == "p1"
    monkeypatch.delenv("RAG_VARIANT")
    assert r.active_variant() == "v3_rerank"                    # the shipped, evaluated variant is the default
