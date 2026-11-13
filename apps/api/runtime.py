"""Shared runtime for API and worker: toolboxes, graphs, event bus and the run executor.

The executor is the single place that drives a graph thread (start or resume), streams node events to the bus
(SSE in the UI), mirrors state into the `runs` table, and handles failures (degraded mode, dead-letter).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict
from typing import Any, AsyncIterator

from langgraph.types import Command

from agent.checkpoint import make_checkpointer
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from agent.marketplace_port import MarketplaceUnavailable
from agent.mcp_client import CURRENT, MCPToolbox, default_connections
from agent.memory import promotion_rules as mem
from agent.memory.store import make_store
from agent.tracing import setup as tracing_setup, span
from apps.api import db

TERMINAL = {"submitted", "skipped", "watch", "rejected", "blocked", "needs_attention", "dead_letter", "sent", "scam_flagged"}


# ------------------------------------------------------------------ event bus (Redis pub/sub if reachable, else in-process)
class Bus:
    def __init__(self):
        self.local: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self.redis = None

    async def start(self, url: str | None):
        if url:
            try:
                import redis.asyncio as aioredis
                r = aioredis.from_url(url); await r.ping(); self.redis = r
            except Exception:  # noqa: BLE001
                self.redis = None

    async def publish(self, thread: str, ev: dict):
        ev = {"ts": time.time(), **ev}
        for q in list(self.local[thread]):
            q.put_nowait(ev)
        if self.redis:
            await self.redis.publish(f"gigbid:{thread}", json.dumps(ev, default=str))

    async def subscribe(self, thread: str) -> AsyncIterator[dict]:
        if self.redis:                                   # cross-process (API <-> worker)
            ps = self.redis.pubsub(); await ps.subscribe(f"gigbid:{thread}")
            try:
                while True:
                    m = await ps.get_message(ignore_subscribe_messages=True, timeout=15)
                    yield json.loads(m["data"]) if m else {"type": "keepalive"}
            finally:
                await ps.close()
        else:
            q: asyncio.Queue = asyncio.Queue(); self.local[thread].append(q)
            try:
                while True:
                    try:
                        yield await asyncio.wait_for(q.get(), 15)
                    except asyncio.TimeoutError:
                        yield {"type": "keepalive"}
            finally:
                self.local[thread].remove(q)


class Runtime:
    def __init__(self):
        self.store = None
        self.checkpointer = None
        self.bus = Bus()
        self._toolboxes: dict[str, Any] = {}
        self._indexes: dict[str, Any] = {}
        self._graphs: dict[tuple, Any] = {}
        self.backend = os.environ.get("GIGBID_TOOLS", "mcp")           # mcp | local
        self.impl = None                                                 # test hook: offline node implementations

    async def start(self):
        tracing_setup()
        await db.init()
        self.store = make_store()
        self.checkpointer = await make_checkpointer()
        await self.bus.start(os.environ.get("REDIS_URL"))
        return self

    # ---- tools ------------------------------------------------------------------------------------------------
    async def toolbox(self, persona: str, user_id: str):
        if self.backend == "local":
            from agent.tools import LocalToolbox
            from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
            base = self._toolboxes.get(persona)
            if base is None:
                base = self._toolboxes[persona] = LocalToolbox(persona, GigSimAdapter(user=user_id))
            scoped = object.__new__(LocalToolbox); scoped.__dict__.update(base.__dict__)
            scoped.mp = GigSimAdapter(user=user_id)
            return scoped
        tb = self._toolboxes.get(persona)
        if tb is None:
            tb = self._toolboxes[persona] = await MCPToolbox(default_connections(persona)).start()
        return tb

    def health(self) -> dict:
        if self.backend == "mcp":
            return {n: t.health() for n, t in self._toolboxes.items()} or {"mcp": "not started"}
        return {"local": {"up": True}}

    async def graph(self, kind: str, persona: str, user_id: str):
        key = (kind, persona, user_id)
        if key not in self._graphs:
            tb = await self.toolbox(persona, user_id)
            self._graphs[key] = (build_bid_graph(tb, self.store, self.checkpointer, self.impl) if kind == "bid"
                                 else build_conversation_graph(tb, self.checkpointer))
        return self._graphs[key]

    # ---- executor -----------------------------------------------------------------------------------------------
    async def execute(self, thread_id: str, user: dict, kind: str, payload: Any, trace_id: str | None = None, checkpoint_id: str | None = None):
        """Start (payload=dict) or resume (payload=Command) a graph thread; stream events; mirror state to `runs`."""
        persona = user["persona"]
        graph = await self.graph(kind, persona, user["id"])
        cfg = {"configurable": {"thread_id": thread_id, **({"checkpoint_id": checkpoint_id} if checkpoint_id else {})}, "metadata": {"user_id": user["id"], "trace_id": trace_id}}
        tok = CURRENT.set({"user": user["id"], "trace_id": trace_id or thread_id})
        t0 = time.time()
        await db.run("UPDATE runs SET status='running', updated_at=now(), error=NULL WHERE thread_id=%s AND user_id=%s", thread_id, user["id"])
        await self.bus.publish(thread_id, {"type": "run_started", "thread_id": thread_id})
        try:
            with span("run", trace_id=trace_id or thread_id, thread_id=thread_id, user_id=user["id"], kind=kind):
                async for chunk in graph.astream(payload, cfg, stream_mode="updates"):
                    for node, upd in chunk.items():
                        if node == "__interrupt__":
                            continue
                        await self.bus.publish(thread_id, {"type": "node", "node": node, "update": _brief(upd)})
            await self.sync(thread_id, user, kind, graph, cfg, time.time() - t0)
        except MarketplaceUnavailable as e:
            await db.run("UPDATE runs SET status='waiting_marketplace', error=%s, updated_at=now() WHERE thread_id=%s AND user_id=%s",
                         str(e)[:300], thread_id, user["id"])
            await self.bus.publish(thread_id, {"type": "degraded", "message": "Marketplace unavailable; work queued and will resume automatically."})
        except Exception as e:  # noqa: BLE001 - dead-letter state after node retries are exhausted
            await db.run("UPDATE runs SET status='dead_letter', error=%s, updated_at=now() WHERE thread_id=%s AND user_id=%s",
                         f"{type(e).__name__}: {e}"[:500], thread_id, user["id"])
            await self.bus.publish(thread_id, {"type": "error", "message": str(e)[:300]})
        finally:
            CURRENT.reset(tok)

    async def sync(self, thread_id, user, kind, graph, cfg, elapsed):
        st = await graph.aget_state(cfg)
        v = st.values or {}
        pending = bool(st.tasks and any(t.interrupts for t in st.tasks))
        status = "awaiting_approval" if pending else v.get("status", "done")
        if kind == "bid":
            fit = (v.get("fit_report") or {}).get("score"); risk = (v.get("risk_report") or {}).get("score")
            price = (v.get("price_quote") or {}).get("amount")
            outcome = v.get("outcome") or {}
            summary = {"decision": v.get("decision"), "unsupported_before": v.get("unsupported_before"),
                       "unsupported_after": v.get("unsupported_after"), "revisions": v.get("revision"),
                       "approval": {k: v for k, v in (v.get("approval") or {}).items() if k in ("action", "reason", "diff")},
                       "compliance": v.get("compliance"), "errors": v.get("errors")}
            await db.run("""UPDATE runs SET status=%s, fit=%s, risk=%s, decision=%s, price=%s, tokens=%s, cost_usd=%s, latency_s=latency_s+%s,
                            proposal_id=COALESCE(%s, proposal_id), summary=%s, updated_at=now() WHERE thread_id=%s AND user_id=%s""",
                         status, fit, risk, (v.get("decision") or {}).get("action"), price, v.get("tokens", 0), v.get("cost_usd", 0), elapsed,
                         outcome.get("proposal_id"), db.J(summary), thread_id, user["id"])
        else:
            await db.run("UPDATE runs SET status=%s, summary=%s, updated_at=now() WHERE thread_id=%s AND user_id=%s", status,
                         db.J({"intent": v.get("intent"), "reply": v.get("reply")}), thread_id, user["id"])
        await self.bus.publish(thread_id, {"type": "status", "status": status})

    async def pending_payload(self, thread_id: str, user: dict, kind: str = "bid") -> dict | None:
        graph = await self.graph(kind, user["persona"], user["id"])
        st = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        for t in st.tasks or []:
            if t.interrupts:
                return t.interrupts[0].value
        return None

    async def resume(self, thread_id: str, user: dict, kind: str, decision: dict, trace_id: str | None = None):
        await self.execute(thread_id, user, kind, Command(resume=decision), trace_id)


def _brief(upd: Any) -> Any:
    """Small, UI-safe summary of a node update (no raw evidence blobs)."""
    if not isinstance(upd, dict):
        return None
    out = {}
    for k, v in upd.items():
        if k in ("trace",) and v:
            out["trace"] = v[-1]
        elif k in ("status", "decision", "price_quote", "revision", "unsupported_before", "unsupported_after", "tokens", "cost_usd"):
            out[k] = v
        elif k in ("risk_report", "fit_report"):
            out[k] = {"score": v.get("score"), "flags": v.get("flags"), "missing": v.get("missing_skills")}
        elif k == "critiques" and v:
            out["critique"] = {"approved": v[-1]["approved"], "issues": v[-1]["issues"]}
    return out


RUNTIME = Runtime()
