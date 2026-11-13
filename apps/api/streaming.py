"""SSE bridge: replays the run so far from the checkpoint, then streams live LangGraph node updates from the event bus."""
from __future__ import annotations

import json

from sse_starlette.sse import EventSourceResponse

from apps.api import db
from apps.api.runtime import RUNTIME, TERMINAL


async def run_stream(thread_id: str, user: dict, kind: str = "bid"):
    row = await db.one("SELECT status FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"])
    if not row:
        return None

    async def gen():
        graph = await RUNTIME.graph(kind, user["persona"], user["id"])
        st = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        for t in (st.values or {}).get("trace", []):                         # replay what already happened
            yield {"event": "node", "data": json.dumps({"type": "node", "node": t["node"], "update": {"trace": t}, "replay": True})}
        cur = (await db.one("SELECT status FROM runs WHERE thread_id=%s", thread_id))["status"]
        yield {"event": "status", "data": json.dumps({"type": "status", "status": cur})}
        if cur in TERMINAL or cur in ("awaiting_approval", "dead_letter"):
            return
        async for ev in RUNTIME.bus.subscribe(thread_id):
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev, default=str)}
            if ev.get("type") == "status" and (ev["status"] in TERMINAL or ev["status"] in ("awaiting_approval", "dead_letter")):
                return
            if ev.get("type") in ("degraded", "error"):
                return

    return EventSourceResponse(gen(), ping=15)
