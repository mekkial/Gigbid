import uuid

import httpx
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graphs.conversation_graph import build_conversation_graph
from agent.handoffs import MessageIntent, ReplyDraft
from gigsim import app as g
from tests.integration.conftest import dev_jobs  # noqa: F401  (fixtures)


async def make_thread(toolbox):
    """Create + submit a proposal on GigSim so a client reply thread exists."""
    mp = toolbox.mp
    for j in (await mp.search_jobs("", 40)):
        d = await mp.create_proposal_draft({"job_id": j["job_id"], "cover_letter": "I recently delivered similar work. " * 10, "bid_amount": 100}, uuid.uuid4().hex)
        r = await mp.submit_proposal(d["proposal_id"], uuid.uuid4().hex)
        if r.get("outcome") != "ignore":
            return d["proposal_id"]
    raise AssertionError("no client replied")


def stub(intent, text="Happy to help; here is more detail.", slots=None):
    async def respond(tools, pid, msg, hint=""):
        return ReplyDraft(proposal_id=pid, intent=MessageIntent(intent=intent), text=text, proposed_slots=slots or [])
    return respond


async def test_reply_requires_approval_then_sends_once(toolbox):
    pid = await make_thread(toolbox)
    graph = build_conversation_graph(toolbox, MemorySaver(), stub("question"))
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    await graph.ainvoke({"user_id": "u", "proposal_id": pid}, cfg)
    assert (await graph.aget_state(cfg)).next == ("approval",)
    n0 = len(await toolbox.mp.list_messages(pid))
    out = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
    assert out["status"] == "sent" and len(await toolbox.mp.list_messages(pid)) == n0 + 1


async def test_scam_signal_is_flagged_not_answered(toolbox):
    pid = await make_thread(toolbox)
    graph = build_conversation_graph(toolbox, MemorySaver(), stub("scam_signal"))
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    n0 = len(await toolbox.mp.list_messages(pid))
    out = await graph.ainvoke({"user_id": "u", "proposal_id": pid}, cfg)
    assert out["status"] == "scam_flagged" and len(await toolbox.mp.list_messages(pid)) == n0


async def test_contact_details_stripped_from_reply(toolbox):
    pid = await make_thread(toolbox)
    graph = build_conversation_graph(toolbox, MemorySaver(), stub("question", "Sure! Message me on WhatsApp +92 300 1112233 instead."))
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    await graph.ainvoke({"user_id": "u", "proposal_id": pid}, cfg)
    payload = (await graph.aget_state(cfg)).tasks[0].interrupts[0].value
    assert "WhatsApp" not in payload["draft"] and "300" not in payload["draft"]


async def test_reject_sends_nothing(toolbox):
    pid = await make_thread(toolbox)
    graph = build_conversation_graph(toolbox, MemorySaver(), stub("negotiation"))
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    await graph.ainvoke({"user_id": "u", "proposal_id": pid}, cfg)
    n0 = len(await toolbox.mp.list_messages(pid))
    out = await graph.ainvoke(Command(resume={"action": "reject", "reason": "wrong tone"}), cfg)
    assert out["status"] == "rejected" and len(await toolbox.mp.list_messages(pid)) == n0
