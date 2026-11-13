import uuid

from langgraph.types import Command

from tests.integration.conftest import dev_jobs

JOBS = dev_jobs()
GOOD = next(j for j in JOBS if j["gold"]["decision"] == "bid" and not j["gold"]["injected"] and "duplicate_of" not in j)
SCAM = next(j for j in JOBS if j["gold"]["scam"] and "duplicate_of" not in j)
INJ = next(j for j in JOBS if j["gold"]["injected"] and "duplicate_of" not in j)


def cfg(tid=None):
    return {"configurable": {"thread_id": tid or str(uuid.uuid4())}}


def init(job, user=None):
    return {"job": job, "user_id": user or f"u-{uuid.uuid4().hex[:6]}", "persona": "ai_ml", "settings": {"floor_hourly": 30}}


async def test_scam_is_skipped_before_any_writing(make_graph):
    g, _, _ = make_graph()
    out = await g.ainvoke(init(SCAM), cfg())
    assert out["status"] == "skipped" and out["decision"]["action"] == "skip"
    assert "draft" not in out and "outcome" not in out
    nodes = [t["node"] for t in out["trace"]]
    assert "writer" not in nodes and {"analyst", "risk_assessor", "fit_matcher"} <= set(nodes)


async def test_injected_job_still_evaluated_and_flagged(make_graph):
    g, _, _ = make_graph()
    out = await g.ainvoke(init(INJ), cfg())
    assert out["risk_report"]["injection_detected"] is True
    assert out["decision"]["action"] == "bid"          # instruction ignored, job judged on merit


async def test_critic_loop_bounded_at_two_revisions(make_graph):
    g, _, _ = make_graph(critic_script=[False, False, False, False, False])
    c = cfg()
    await g.ainvoke(init(GOOD), c)
    st = g.get_state(c)
    assert len([t for t in st.values["trace"] if t["node"] == "writer"]) <= 3      # initial + 2 revisions
    assert st.next == ("approval",)                       # paused for the human, never auto-sent


async def test_approve_submits_exactly_once_even_if_resumed_twice(make_graph, toolbox):
    g, _, _ = make_graph()
    c = cfg(); await g.ainvoke(init(GOOD, "u-once"), c)
    before = (await toolbox.mp.get_connects_balance())["balance"]
    out = await g.ainvoke(Command(resume={"action": "approve"}), c)
    assert out["status"] == "submitted"
    mid = (await toolbox.mp.get_connects_balance())["balance"]
    # replay the final node with the same thread (same idempotency keys): no second spend
    g.update_state(c, {"status": "approved"}, as_node="approval")
    await g.ainvoke(None, c)
    after = (await toolbox.mp.get_connects_balance())["balance"]
    assert before - mid == GOOD["connects_cost"] and mid == after


async def test_reject_never_submits(make_graph, toolbox):
    g, _, _ = make_graph(); c = cfg(); await g.ainvoke(init(GOOD), c)
    bal = (await toolbox.mp.get_connects_balance())["balance"]
    out = await g.ainvoke(Command(resume={"action": "reject", "reason": "too pushy"}), c)
    assert out["status"] == "rejected" and (await toolbox.mp.get_connects_balance())["balance"] == bal


async def test_edit_is_diffed_rechecked_and_feeds_style_memory(make_graph):
    g, store, _ = make_graph(); user = f"u-{uuid.uuid4().hex[:5]}"
    goods = [j for j in JOBS if j["gold"]["decision"] == "bid" and not j["gold"]["injected"] and "duplicate_of" not in j][:3]
    for job in goods:
        c = cfg(); await g.ainvoke(init(job, user), c)
        st = g.get_state(c).tasks[0].interrupts[0].value
        edited = " ".join(st["send_text"].split(". ")[1:])             # user always cuts the first sentence
        out = await g.ainvoke(Command(resume={"action": "edit", "text": edited}), c)
        assert out["approval"]["diff"]
    rules = [i.value["rule"] for i in store.search(("style", user))]
    assert any("first sentence" in r for r in rules)


async def test_edit_with_contact_details_is_cleaned_by_compliance(make_graph):
    g, _, _ = make_graph(); c = cfg(); await g.ainvoke(init(GOOD), c)
    st = g.get_state(c).tasks[0].interrupts[0].value
    out = await g.ainvoke(Command(resume={"action": "edit", "text": st["send_text"] + " Contact me on WhatsApp +92 300 1234567."}), c)
    assert "WhatsApp" not in out["send_text"] and "off_platform_contact" in out["approval"]["violations"]


async def test_resume_after_crash_uses_persisted_checkpoint(make_graph, toolbox, tmp_path):
    """Simulated API crash: graph object discarded while waiting for approval; a new graph on the same DB resumes it."""
    from agent.checkpoint import make_checkpointer
    cp = await make_checkpointer(url="", sqlite_path=str(tmp_path / "cp.sqlite"))
    g1, store, _ = make_graph(cp=cp); c = cfg(); await g1.ainvoke(init(GOOD, "u-crash"), c)
    del g1
    cp2 = await make_checkpointer(url="", sqlite_path=str(tmp_path / "cp.sqlite"))         # "restart": fresh connection
    g2, _, _ = make_graph(cp=cp2, store=store)
    assert (await g2.aget_state(c)).next == ("approval",)
    out = await g2.ainvoke(Command(resume={"action": "approve"}), c)
    assert out["status"] == "submitted"
