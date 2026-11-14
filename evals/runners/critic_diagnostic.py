"""3-job diagnostic of the Critic loop: prints each round's critique (approved, grounding, personalisation, length) and the final draft length.
Run: MODEL_PROFILE=local python -m evals.runners.critic_diagnostic   (results of the before/after run: evals/results/critic_diagnostic.json)"""
import asyncio
import os
import uuid
os.environ.setdefault("MODEL_PROFILE", "local")
from evals.runners.common import marketplace
from agent.graphs.bid_graph import build_bid_graph
from agent.tools import LocalToolbox
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from evals.runners.rag_eval import load_jobs

async def main():
    jobs = [j for j in load_jobs("ai_ml") if j["kind"] == "good"][:3]
    tb = LocalToolbox("ai_ml", marketplace("diag")); g = build_bid_graph(tb, InMemoryStore(), MemorySaver())
    for j in jobs:
        cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
        out = await g.ainvoke({"job": j, "user_id": "diag", "persona": "ai_ml", "settings": {"floor_hourly": 30}}, cfg)
        print(f"\n=== {j['job_id']}  revisions={out.get('revision')}  rounds={len(out['critiques'])}")
        for i, c in enumerate(out["critiques"]):
            print(f"  round {i+1}: approved={c['approved']} grounding={c['grounding']} personalisation={c['personalisation']} length_ok={c['length_ok']}")
            for iss in c["issues"][:4]: print("      -", iss[:150])
        d = out["draft"]["cover_letter"]; print("  final draft words:", len(d.split()), "| unsupported claims left:", sum(c['verdict']=='unsupported' for c in out['claims']))
asyncio.run(main())
