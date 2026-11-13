from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from apps.api import db, queue
from apps.api.auth.security import current_user
from apps.api.routers.jobs import COLS
from apps.api.runtime import RUNTIME
from apps.api.schemas.models import RunOut
from apps.api.streaming import run_stream

router = APIRouter(tags=["runs"])


def trace_url(thread_id: str) -> str | None:
    host = os.environ.get("LANGFUSE_HOST")
    return f"{host}/traces?search={thread_id}" if host and os.environ.get("LANGFUSE_PUBLIC_KEY") else None


@router.get("/runs", response_model=list[RunOut])
async def list_runs(user: dict = Depends(current_user)):
    return await db.fetch(f"SELECT {COLS} FROM runs WHERE user_id=%s ORDER BY updated_at DESC LIMIT 100", user["id"])


@router.get("/runs/{thread_id:path}/stream")
async def stream(thread_id: str, user: dict = Depends(current_user)):
    kind = "conv" if thread_id.startswith("conv:") else "bid"
    resp = await run_stream(thread_id, user, kind)
    if resp is None:
        raise HTTPException(404, "run not found")
    return resp


@router.get("/runs/{thread_id:path}/history")
async def history(thread_id: str, user: dict = Depends(current_user)):
    """Checkpoint history: every superstep, usable for replay from any node."""
    if not await db.one("SELECT 1 FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"]):
        raise HTTPException(404, "run not found")
    graph = await RUNTIME.graph("bid", user["persona"], user["id"])
    out = []
    async for s in graph.aget_state_history({"configurable": {"thread_id": thread_id}}):
        out.append({"checkpoint_id": s.config["configurable"]["checkpoint_id"], "next": list(s.next), "step": s.metadata.get("step"),
                    "status": (s.values or {}).get("status")})
    return out


@router.post("/runs/{thread_id:path}/replay")
async def replay(thread_id: str, checkpoint_id: str, user: dict = Depends(current_user)):
    if not await db.one("SELECT 1 FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"]):
        raise HTTPException(404, "run not found")
    await queue.enqueue("replay_run", user["id"], thread_id, checkpoint_id)
    return {"queued": True}


@router.get("/runs/{thread_id:path}")
async def get_run(thread_id: str, user: dict = Depends(current_user)):
    run = await db.one(f"SELECT {COLS} FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"])
    if not run:
        raise HTTPException(404, "run not found")
    kind = "conv" if thread_id.startswith("conv:") else "bid"
    graph = await RUNTIME.graph(kind, user["persona"], user["id"])
    st = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    return {"run": run, "trace": (st.values or {}).get("trace", []), "trace_url": trace_url(thread_id),
            "totals": {k: (st.values or {}).get(k) for k in ("steps", "tokens", "cost_usd")}}
