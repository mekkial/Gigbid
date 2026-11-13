"""Conversation graph (one thread per client conversation):
read_messages -> liaison (classify + draft reply/slots) -> [scam_signal: flag & stop] -> approval(interrupt) -> send (+ tentative hold).
Nothing is sent before the human approves; the send uses an idempotency key derived from the thread id."""
from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt

from agent.handoffs import ReplyDraft
from agent.nodes import client_liaison
from agent.nodes.compliance import check
from agent.state import ConvState


def build_conversation_graph(tools, checkpointer=None, respond=None):
    respond = respond or client_liaison.respond

    async def read_messages(state: ConvState):
        t0 = time.time()
        msgs = await tools.call("client_liaison", "list_messages", proposal_id=state["proposal_id"])
        client_msgs = [m for m in msgs if m["from"] == "client"]
        if not client_msgs:
            return {"status": "no_new_messages", "steps": 1}
        return {"message": client_msgs[-1]["text"], "status": "running", "steps": 1,
                "trace": [{"node": "read_messages", "latency_s": round(time.time() - t0, 3)}]}

    def after_read(state):
        return END if state.get("status") == "no_new_messages" else "liaison"

    async def liaison(state: ConvState):
        t0 = time.time()
        r: ReplyDraft = await respond(tools, state["proposal_id"], state["message"])
        v = check(r.text.ljust(150))                      # compliance on outgoing text (length rule not applied to messages)
        upd = {"intent": r.intent.model_dump(), "reply": r.model_dump() | {"text": v.cleaned_text.strip(), "violations": v.violations},
               "steps": 1, "trace": [{"node": "client_liaison", "latency_s": round(time.time() - t0, 3), "intent": r.intent.intent}]}
        if r.intent.intent == "scam_signal":
            upd["status"] = "scam_flagged"                # never reply to a scam; surface it to the user
        return upd

    def after_liaison(state):
        return END if state.get("status") == "scam_flagged" else "approval"

    async def approval(state: ConvState):
        resp = interrupt({"kind": "message_approval", "proposal_id": state["proposal_id"], "client_message": state["message"],
                          "intent": state["intent"], "draft": state["reply"]["text"], "proposed_slots": state["reply"]["proposed_slots"]})
        if resp.get("action") == "reject":
            return {"approval": resp, "status": "rejected", "steps": 1}
        text = resp.get("text", state["reply"]["text"])
        v = check(text.ljust(150))
        if not v.allowed and "length_out_of_bounds" not in v.violations:
            return {"approval": resp, "status": "blocked", "steps": 1}
        return {"approval": resp | {"text": v.cleaned_text.strip()}, "status": "approved", "steps": 1}

    def after_approval(state):
        return "send" if state.get("status") == "approved" else END

    async def send(state: ConvState, config):
        tid = config["configurable"]["thread_id"]
        await tools.call("client_liaison", "send_message", proposal_id=state["proposal_id"], text=state["approval"]["text"],
                               idempotency_key=f"{tid}:send")
        slot = state["approval"].get("slot")
        if slot and state["intent"]["intent"] == "interview_request":
            await tools.call("client_liaison", "create_tentative_hold", slot=slot, title=f"Interview ({state['proposal_id']})")
        return {"status": "sent", "steps": 1}

    g = StateGraph(ConvState)
    retry = RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0)
    g.add_node("read_messages", read_messages, retry_policy=retry)
    g.add_node("liaison", liaison, retry_policy=retry)
    g.add_node("approval", approval)
    g.add_node("send", send, retry_policy=retry)
    g.add_edge(START, "read_messages")
    g.add_conditional_edges("read_messages", after_read, ["liaison", END])
    g.add_conditional_edges("liaison", after_liaison, ["approval", END])
    g.add_conditional_edges("approval", after_approval, ["send", END])
    g.add_edge("send", END)
    return g.compile(checkpointer=checkpointer)
