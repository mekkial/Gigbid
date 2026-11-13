from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException

from agent.marketplace_port import MarketplaceUnavailable
from apps.api import db, queue
from apps.api.service import create_run
from apps.api.auth.security import current_user
from apps.api.runtime import RUNTIME
from apps.api.schemas.models import RunOut, SavedSearchIn, SavedSearchOut, ScoutIn

router = APIRouter(tags=["jobs"])
COLS = "thread_id, job_id, kind, status, title, category, fit, risk, decision, price, connects, tokens, cost_usd, latency_s, proposal_id, outcome, summary, error"


@router.get("/jobs", response_model=list[RunOut])
async def inbox(status: str | None = None, min_fit: float = 0, q: str | None = None, user: dict = Depends(current_user)):
    rows = await db.fetch(f"SELECT {COLS} FROM runs WHERE user_id=%s AND kind='bid' AND COALESCE(fit,0) >= %s "
                          "AND (%s::text IS NULL OR status=%s) AND (%s::text IS NULL OR title ILIKE %s) "
                          "ORDER BY (status='awaiting_approval') DESC, COALESCE(fit,0) DESC, updated_at DESC LIMIT 200",
                          user["id"], min_fit, status, status, q, f"%{q}%" if q else None)
    return rows


@router.post("/jobs/scout")
async def scout(body: ScoutIn, user: dict = Depends(current_user)):
    """Queue a scouting pass (runs in the worker): search, de-duplicate, create runs for new jobs."""
    await queue.enqueue("scout", user["id"], body.query, body.limit)
    return {"queued": True}


@router.get("/jobs/{job_id}")
async def job_detail(job_id: str, user: dict = Depends(current_user)):
    run = await db.one(f"SELECT {COLS} FROM runs WHERE thread_id=%s AND user_id=%s", f"{user['id']}:{job_id}", user["id"])
    if not run:
        raise HTTPException(404, "job not in your inbox")
    graph = await RUNTIME.graph("bid", user["persona"], user["id"])
    st = await graph.aget_state({"configurable": {"thread_id": run["thread_id"]}})
    v = st.values or {}
    keep = ("job", "job_spec", "risk_report", "fit_report", "evidence", "decision", "price_quote", "unsupported_before", "unsupported_after")
    return {"run": run, **{k: v.get(k) for k in keep}}


@router.post("/jobs/{job_id}/analyse")
async def analyse(job_id: str, user: dict = Depends(current_user)):
    tb = await RUNTIME.toolbox(user["persona"], user["id"])
    try:
        job = await tb.call("scout", "get_job", job_id=job_id)
    except MarketplaceUnavailable as e:
        raise HTTPException(503, f"marketplace_unavailable: {e}")
    return {"created": await create_run(user, job)}


@router.post("/jobs/{job_id}/skip")
async def skip(job_id: str, user: dict = Depends(current_user)):
    n = await db.fetch("UPDATE runs SET status='skipped', decision='skip', updated_at=now() WHERE thread_id=%s AND user_id=%s "
                       "AND status NOT IN ('submitted') RETURNING 1", f"{user['id']}:{job_id}", user["id"])
    if not n:
        raise HTTPException(404, "nothing to skip")
    return {"ok": True}


@router.get("/saved-searches", response_model=list[SavedSearchOut])
async def list_searches(user: dict = Depends(current_user)):
    return await db.fetch("SELECT id, query, interval_min FROM saved_searches WHERE user_id=%s ORDER BY id", user["id"])


@router.post("/saved-searches", response_model=SavedSearchOut)
async def add_search(body: SavedSearchIn, user: dict = Depends(current_user)):
    from agent.llm import load_config
    if (user["settings"] or {}).get("marketplace_mode") == "upwork_live" and body.interval_min < load_config()["marketplace"]["live"]["min_poll_interval_min"]:
        raise HTTPException(422, f"live mode requires an interval of at least {load_config()['marketplace']['live']['min_poll_interval_min']} minutes")
    return (await db.fetch("INSERT INTO saved_searches(user_id,query,interval_min) VALUES(%s,%s,%s) RETURNING id, query, interval_min",
                           user["id"], body.query, body.interval_min))[0]


@router.delete("/saved-searches/{sid}")
async def del_search(sid: int, user: dict = Depends(current_user)):
    await db.run("DELETE FROM saved_searches WHERE id=%s AND user_id=%s", sid, user["id"])
    return {"ok": True}
