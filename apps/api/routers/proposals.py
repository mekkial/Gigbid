from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException

from agent.llm import chat
from agent.memory import promotion_rules as mem
from agent.prompts import load_prompt, untrusted
from apps.api import db
from apps.api.auth.security import current_user
from apps.api.runtime import RUNTIME
from apps.api.schemas.models import PipelineCard, RegenerateIn, RegenerateOut

router = APIRouter(tags=["proposals"])


@router.get("/proposals/{thread_id:path}/studio")
async def studio(thread_id: str, user: dict = Depends(current_user)):
    """Everything the Proposal Studio needs: draft with per-claim evidence, critic/compliance comments, dry-run preview."""
    if not await db.one("SELECT 1 FROM runs WHERE thread_id=%s AND user_id=%s", thread_id, user["id"]):
        raise HTTPException(404, "not found")
    p = await RUNTIME.pending_payload(thread_id, user)
    if p:
        return {"pending": True, **p}
    graph = await RUNTIME.graph("bid", user["persona"], user["id"])
    v = (await graph.aget_state({"configurable": {"thread_id": thread_id}})).values or {}
    return {"pending": False, "draft": (v.get("draft") or {}).get("cover_letter"), "send_text": v.get("send_text"), "claims": v.get("claims", []),
            "evidence": v.get("evidence", []), "risk_report": v.get("risk_report"), "price_quote": v.get("price_quote"),
            "critiques": v.get("critiques", []), "compliance": v.get("compliance")}


@router.post("/proposals/{thread_id:path}/regenerate", response_model=RegenerateOut)
async def regenerate(thread_id: str, body: RegenerateIn, user: dict = Depends(current_user)):
    """Rewrite ONE paragraph, grounded in the same evidence and the user's promoted style rules. Returns text; the user decides."""
    p = await RUNTIME.pending_payload(thread_id, user)
    if not p:
        raise HTTPException(409, "no draft awaiting approval")
    paras = [x for x in re.split(r"\n\s*\n", p["send_text"]) if x.strip()] or [p["send_text"]]
    if body.paragraph_index >= len(paras):
        raise HTTPException(422, "paragraph_index out of range")
    ev = "\n".join(f"[{e['id']}] {e['text'][:400]}" for e in p["evidence"])
    rules = mem.style_rules(RUNTIME.store, user["id"])
    text = chat("writer", load_prompt("regenerate"),
                f"EVIDENCE:\n{ev}\nSTYLE RULES: {rules or 'none'}\nFULL DRAFT:\n{p['send_text']}\n\nREWRITE PARAGRAPH {body.paragraph_index + 1}:\n"
                f"{untrusted('paragraph', paras[body.paragraph_index])}\nINSTRUCTION: {body.instruction or 'make it more specific'}")
    return RegenerateOut(text=text.strip())


STAGE = {"hire": "hired", "interview": "interview", "reply": "replied"}


@router.get("/pipeline", response_model=list[PipelineCard])
async def pipeline(user: dict = Depends(current_user)):
    """Kanban from run state + marketplace events. drafted -> submitted -> viewed -> replied -> interview -> hired / lost."""
    rows = await db.fetch("SELECT thread_id, job_id, title, status, price, proposal_id, outcome, updated_at, "
                          "EXTRACT(EPOCH FROM (now()-updated_at)) AS age FROM runs WHERE user_id=%s AND kind='bid' AND "
                          "status IN ('awaiting_approval','submitted')", user["id"])
    cards = []
    for r in rows:
        if r["status"] == "awaiting_approval":
            stage = "drafted"
        elif r["outcome"] in STAGE:
            stage = STAGE[r["outcome"]]
        elif r["outcome"] == "ignore":
            stage = "viewed" if r["age"] < 120 else "lost"
        else:
            stage = "submitted"
        cards.append(PipelineCard(thread_id=r["thread_id"], job_id=r["job_id"], title=r["title"], stage=stage, price=r["price"], proposal_id=r["proposal_id"]))
    return cards


@router.post("/pipeline/sync")
async def sync_outcomes(user: dict = Depends(current_user)):
    """Pull marketplace events for submitted proposals; promote outcomes to long-term memory via the explicit rule."""
    tb = await RUNTIME.toolbox(user["persona"], user["id"])
    rows = await db.fetch("SELECT thread_id, proposal_id, category, outcome FROM runs WHERE user_id=%s AND status='submitted' AND proposal_id IS NOT NULL", user["id"])
    updated = 0
    for r in rows:
        if r["outcome"]:
            continue
        res = await tb.call("submit", "submit_proposal", proposal_id=r["proposal_id"], idempotency_key=f"{r['thread_id']}:submit")   # replay returns stored outcome
        out = (res or {}).get("outcome")
        if out:
            await db.run("UPDATE runs SET outcome=%s, updated_at=now() WHERE thread_id=%s AND user_id=%s", out, r["thread_id"], user["id"])
            mem.record_outcome(RUNTIME.store, user["id"], r["category"] or "general", {"hire": "won", "interview": "replied", "reply": "replied"}.get(out, "ignored"))
            updated += 1
    return {"updated": updated}
