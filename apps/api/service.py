from __future__ import annotations

from agent.nodes.scout import fingerprint
from apps.api import db, queue


async def create_run(user: dict, job: dict) -> bool:
    """Idempotent: one thread per (user, job) and no re-analysis of a re-posted duplicate. True only if a NEW run was created."""
    tid = f"{user['id']}:{job['job_id']}"
    fp = fingerprint(job)
    if await db.one("SELECT 1 FROM runs WHERE user_id=%s AND fp=%s", user["id"], fp):
        return False
    r = await db.fetch("INSERT INTO runs(thread_id,user_id,job_id,title,category,connects,status,fp) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s) "
                       "ON CONFLICT(thread_id) DO NOTHING RETURNING thread_id", tid, user["id"], job["job_id"], job["title"],
                       job.get("persona_hint", "general"), job.get("connects_cost"), fp)
    if r:
        await queue.enqueue("run_bid", user["id"], job, job_id=f"bid:{tid}")
    return bool(r)
