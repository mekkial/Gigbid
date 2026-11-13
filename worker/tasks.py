"""Worker tasks (Arq on Redis). Scouting and long agent runs never execute inside web requests (E1).
All tasks are idempotent: a worker restart or retried job continues from the LangGraph checkpoint and can never
double-analyse or double-submit (graph threads are keyed by user+job; submit uses thread-derived idempotency keys)."""
from __future__ import annotations

import asyncio
import os

from agent.marketplace_port import MarketplaceUnavailable
from apps.api import db
from apps.api.runtime import RUNTIME, TERMINAL
from apps.api.service import create_run

SEM = asyncio.Semaphore(int(os.environ.get("RUN_CONCURRENCY", "2")))     # polite to LLM and marketplace rate limits


async def _user(uid: str) -> dict:
    return await db.one("SELECT id, email, persona, settings FROM users WHERE id=%s", uid)


async def run_bid(ctx, user_id: str, job: dict):
    user = await _user(user_id)
    tid = f"{user_id}:{job['job_id']}"
    graph = await RUNTIME.graph("bid", user["persona"], user_id)
    st = await graph.aget_state({"configurable": {"thread_id": tid}})
    if st.values and (st.values.get("status") in TERMINAL or any(t.interrupts for t in (st.tasks or []))):
        return                                                              # already finished or waiting on a human
    payload = None if st.next else {"job": job, "user_id": user_id, "persona": user["persona"], "settings": user["settings"] or {}}
    async with SEM:
        await RUNTIME.execute(tid, user, "bid", payload)


async def scout(ctx, user_id: str, query: str, limit: int = 10):
    user = await _user(user_id)
    tb = await RUNTIME.toolbox(user["persona"], user_id)
    s = user["settings"] or {}
    try:
        jobs = await tb.call("scout", "search_jobs", query=query, limit=limit)
    except MarketplaceUnavailable:
        return 0
    n = 0
    for j in jobs:
        if "duplicate_of" in j or (j.get("budget", {}).get("max") or 0) < s.get("min_budget", 0):
            continue
        n += await create_run(user, j)
    return n


async def scout_saved_searches(ctx):
    """Cron: run each saved search no more often than its interval (live mode uses a conservative floor)."""
    rows = await db.fetch("SELECT id, user_id, query, interval_min FROM saved_searches WHERE last_run IS NULL OR last_run < now() - make_interval(mins => interval_min)")
    for r in rows:
        await db.run("UPDATE saved_searches SET last_run=now() WHERE id=%s", r["id"])
        await scout(ctx, r["user_id"], r["query"], 10)


async def resume_run(ctx, user_id: str, thread_id: str, kind: str, decision: dict, trace_id: str | None = None):
    user = await _user(user_id)
    async with SEM:
        await RUNTIME.resume(thread_id, user, kind, decision, trace_id)


async def run_conversation(ctx, user_id: str, thread_id: str, proposal_id: str):
    user = await _user(user_id)
    async with SEM:
        await RUNTIME.execute(thread_id, user, "conv", {"user_id": user_id, "persona": user["persona"], "proposal_id": proposal_id})


async def replay_run(ctx, user_id: str, thread_id: str, checkpoint_id: str):
    user = await _user(user_id)
    async with SEM:
        await RUNTIME.execute(thread_id, user, "bid", None, checkpoint_id=checkpoint_id)


async def retry_waiting(ctx):
    """Cron: marketplace came back? resume runs parked in `waiting_marketplace` from their checkpoints."""
    for r in await db.fetch("SELECT thread_id, user_id FROM runs WHERE status='waiting_marketplace' AND updated_at < now() - interval '15 seconds'"):
        user = await _user(r["user_id"])
        try:
            await (await RUNTIME.toolbox(user["persona"], user["id"])).call("pricing", "get_connects_balance")
        except Exception:  # noqa: BLE001 - still down
            continue
        kind = "conv" if r["thread_id"].startswith("conv:") else "bid"
        await RUNTIME.execute(r["thread_id"], user, kind, None)
