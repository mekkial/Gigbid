"""Background execution (E1): Arq on Redis when available (separate worker process), else in-process tasks."""
from __future__ import annotations

import asyncio
import os

_pool = None
_tasks: set = set()


async def init():
    global _pool
    url = os.environ.get("REDIS_URL")
    if url and os.environ.get("GIGBID_QUEUE", "arq") == "arq":
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            _pool = await create_pool(RedisSettings.from_dsn(url))
        except Exception:  # noqa: BLE001
            _pool = None


async def enqueue(fn_name: str, *args, job_id: str | None = None):
    """Returns True if handed to the worker; else runs inline in this process (dev/test fallback)."""
    if _pool is not None:
        await _pool.enqueue_job(fn_name, *args, _job_id=job_id)          # _job_id makes enqueue idempotent
        return True
    from worker import tasks
    t = asyncio.create_task(getattr(tasks, fn_name)({"inline": True}, *args)); _tasks.add(t); t.add_done_callback(_tasks.discard)
    return False
