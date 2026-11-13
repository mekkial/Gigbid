"""Run representative jobs through the real pipeline with tracing on, so traces exist in Phoenix: a skipped scam, an approved proposal
(with Critic loop if triggered). Usage: PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006 python scripts/trace_demo.py"""
import asyncio, json, os, uuid
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
from evals.runners.common import marketplace   # loads .env, GigSim in-process
from agent import tracing
from agent.graphs.bid_graph import build_bid_graph
from agent.tools import LocalToolbox
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from evals.runners.rag_eval import load_jobs

tracing.setup()


async def main():
    jobs = load_jobs("ai_ml")
    scam = next(j for j in jobs if j["kind"] == "scam"); good = next(j for j in jobs if j["kind"] == "good")
    tb = LocalToolbox("ai_ml", marketplace("trace-demo"))
    g = build_bid_graph(tb, InMemoryStore(), MemorySaver())
    for name, job in (("skipped_scam", scam), ("approved_proposal", good)):
        tid = f"trace-{name}-{uuid.uuid4().hex[:6]}"
        cfg = {"configurable": {"thread_id": tid}}
        with tracing.span("run", trace_id=tid, thread_id=tid, scenario=name):
            out = await g.ainvoke({"job": job, "user_id": "trace-demo", "persona": "ai_ml", "settings": {"floor_hourly": 30}}, cfg)
            if (await g.aget_state(cfg)).next == ("approval",):
                out = await g.ainvoke(Command(resume={"action": "approve"}), cfg)
        print(name, tid, out["status"], "tokens", out.get("tokens"), "cost", round(out.get("cost_usd", 0), 5), [t["node"] for t in out["trace"]])
asyncio.run(main())
import time; time.sleep(6)       # let the batch span processor flush
