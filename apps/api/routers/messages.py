from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from apps.api import db, queue
from apps.api.auth.security import current_user
from apps.api.runtime import RUNTIME

router = APIRouter(tags=["messages"])


@router.get("/messages")
async def threads(user: dict = Depends(current_user)):
    """Client threads for submitted proposals, with whether a reply draft is already waiting for approval."""
    tb = await RUNTIME.toolbox(user["persona"], user["id"])
    rows = await db.fetch("SELECT thread_id, job_id, title, proposal_id FROM runs WHERE user_id=%s AND kind='bid' AND status='submitted' AND proposal_id IS NOT NULL", user["id"])
    out = []
    for r in rows:
        msgs = await tb.call("client_liaison", "list_messages", proposal_id=r["proposal_id"])
        if msgs:
            conv = await db.one("SELECT thread_id, status FROM runs WHERE user_id=%s AND kind='conv' AND job_id=%s ORDER BY created_at DESC LIMIT 1", user["id"], r["proposal_id"])
            out.append({**r, "messages": msgs, "conversation": conv})
    return out


@router.post("/messages/{proposal_id}/respond")
async def respond(proposal_id: str, user: dict = Depends(current_user)):
    """Start the conversation graph for the latest client message (one thread per message; idempotent per message count)."""
    own = await db.one("SELECT 1 FROM runs WHERE user_id=%s AND proposal_id=%s", user["id"], proposal_id)
    if not own:
        raise HTTPException(404, "unknown proposal")
    tb = await RUNTIME.toolbox(user["persona"], user["id"])
    n = len(await tb.call("client_liaison", "list_messages", proposal_id=proposal_id))
    tid = f"conv:{user['id']}:{proposal_id}:{n}"
    made = await db.fetch("INSERT INTO runs(thread_id,user_id,job_id,kind,title,status) VALUES(%s,%s,%s,'conv',%s,'queued') ON CONFLICT DO NOTHING RETURNING thread_id",
                          tid, user["id"], proposal_id, f"Reply to {proposal_id}")
    if made:
        await queue.enqueue("run_conversation", user["id"], tid, proposal_id, job_id=f"conv:{tid}")
    return {"thread_id": tid, "created": bool(made)}
