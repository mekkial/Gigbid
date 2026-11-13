"""Shared helpers for LLM-based evaluation runners."""
from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
import os  # noqa: E402

os.environ["GIGSIM_API_TOKEN"] = "dev-token"

from agent import llm  # noqa: E402
from gigsim import app as gs  # noqa: E402
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter  # noqa: E402

gs.RULES.update(error_rate_5xx=0.0, rate_limit_per_minute=10_000_000)
gs.RULES["connects"]["starting_balance"] = 10_000_000


def marketplace(user="eval"):
    return GigSimAdapter(user=user, client=httpx.AsyncClient(transport=httpx.ASGITransport(app=gs.app), base_url="http://t"), backoff=0.01)


@contextmanager
def model_config(overrides: dict[str, str] | None):
    old = dict(llm.OVERRIDES)
    llm.OVERRIDES.clear(); llm.OVERRIDES.update(overrides or {})
    try:
        yield
    finally:
        llm.OVERRIDES.clear(); llm.OVERRIDES.update(old)


async def tracked(coro_fn, *a, **k):
    """Run an async fn, returning (result, latency_s, tokens, cost_usd) using the per-call LLM usage collector."""
    usage: list = []
    tok = llm.USAGE.set(usage)
    t0 = time.time()
    try:
        res = await coro_fn(*a, **k)
    finally:
        llm.USAGE.reset(tok)
    return res, time.time() - t0, sum(u[1] + u[2] for u in usage), sum(llm.cost_usd(m, a_, b) for m, a_, b in usage)


async def gather_limited(coros, limit=6):
    sem = asyncio.Semaphore(limit)

    async def run(c):
        async with sem:
            return await c
    return await asyncio.gather(*[run(c) for c in coros], return_exceptions=True)


def pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))], 3) if xs else None


def f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0}
