"""Human approvals: resume the interrupted LangGraph thread. A pending approval survives refresh and restarts (it lives in the checkpoint)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api import db, queue
from apps.api.auth.security import current_user
from apps.api.runtime import RUNTIME
from apps.api.schemas.models import DecisionIn

router = APIRouter(tags=["approvals"])


def kind_of(thread_id: str) -> str:
    return "conv" if thread_id.startswith("conv:") else "bid"


@router.get("/approvals")
async def pending(user: dict = Depends(current_user)):
    rows = await db.fetch("SELECT thread_id, job_id, title, kind, price, fit, risk, updated_at FROM runs WHERE user_id=%s "
                          "AND status='awaiting_approval' ORDER BY updated_at DESC", user["id"])
    return rows


@router.get("/approvals/{thread_id:path}")
async def payload(thread_id: str, user: dict = Depends(current_user)):
    if not await db.one("SELECT 1 FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"]):
        raise HTTPException(404, "not found")
    p = await RUNTIME.pending_payload(thread_id, user, kind_of(thread_id))
    if p is None:
        raise HTTPException(404, "no pending approval")
    return p


@router.post("/approvals/{thread_id:path}")
async def decide(thread_id: str, body: DecisionIn, request: Request, user: dict = Depends(current_user)):
    if body.action == "edit" and not body.text:
        raise HTTPException(422, "edit requires text")
    if body.action == "reject" and not body.reason:
        raise HTTPException(422, "reject requires a reason")
    # atomic check-and-set: a double click or retry cannot resume (and so cannot submit) twice
    claimed = await db.fetch("UPDATE runs SET status='resuming', updated_at=now() WHERE thread_id=%s AND user_id=%s "
                             "AND status='awaiting_approval' RETURNING thread_id", thread_id, user["id"])
    if not claimed:
        raise HTTPException(409, "no pending approval for this thread (already decided?)")
    await queue.enqueue("resume_run", user["id"], thread_id, kind_of(thread_id), body.model_dump(exclude_none=True),
                        getattr(request.state, "trace_id", None))
    return {"accepted": True}
