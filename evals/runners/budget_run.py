"""E5: measured latency/cost vs the DECLARED budgets (agent/config.yaml: declared_budgets), SEQUENTIAL (concurrency 1) so queueing behind
other jobs or the rate limiter's own waits are not mixed into the numbers. Per job analysed and per proposal.
Run: MODEL_PROFILE=open|local python -m evals.runners.budget_run --analysis 8 --proposals 4"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from agent.llm import active_profile, active_profile_info, load_config
from agent.tools import LocalToolbox
from evals.runners.common import marketplace, pct, tracked
from evals.runners.decision_eval import analyse_job
from evals.runners.rag_eval import ROOT, load_jobs


async def main(n_an, n_pr):
    prof = active_profile(); B = load_config()["declared_budgets"]["open" if prof == "open" else "local"]
    tb = LocalToolbox("ai_ml", marketplace("budget"))
    jobs = load_jobs("ai_ml", 0)
    mixed = [j for k in ("good", "skip", "scam", "lowball") for j in [x for x in jobs if x["kind"] == k][: max(1, n_an // 4)]][:n_an]
    an = []
    for j in mixed:
        _, lat, tok, cost = await tracked(analyse_job, tb, j, 30)
        an.append((lat, tok, cost))
    g = build_bid_graph(tb, InMemoryStore(), MemorySaver())
    pr = []
    for j in [x for x in jobs if x["kind"] == "good"][:n_pr]:
        cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
        out = await g.ainvoke({"job": j, "user_id": "budget", "persona": "ai_ml", "settings": {"floor_hourly": 30}}, cfg)
        if (await g.aget_state(cfg)).next == ("approval",):
            pr.append((sum(t["latency_s"] for t in out["trace"]), out.get("tokens", 0), out.get("cost_usd", 0), out.get("revision", 0)))
            await g.ainvoke(Command(resume={"action": "reject", "reason": "budget run"}), cfg)
    f = lambda rows, i: [r[i] for r in rows]  # noqa: E731
    res = {"llm": active_profile_info(), "declared": B, "concurrency": 1, "measured": {
        "analysis": {"n": len(an), "p50_latency_s": pct(f(an, 0), .5), "p95_latency_s": pct(f(an, 0), .95), "tokens_mean": round(sum(f(an, 1)) / max(1, len(an))), "list_cost_usd_mean": round(sum(f(an, 2)) / max(1, len(an)), 6)},
        "proposal": {"n": len(pr), "p50_latency_s": pct(f(pr, 0), .5), "p95_latency_s": pct(f(pr, 0), .95), "tokens_mean": round(sum(f(pr, 1)) / max(1, len(pr))), "list_cost_usd_mean": round(sum(f(pr, 2)) / max(1, len(pr)), 6), "avg_revisions": round(sum(f(pr, 3)) / max(1, len(pr)), 2)}}}
    m = res["measured"]
    res["verdict"] = {"analysis_p95_within_budget": m["analysis"]["p95_latency_s"] <= B["analysis_p95_s"], "proposal_p95_within_budget": m["proposal"]["p95_latency_s"] <= B["proposal_p95_s"], "proposal_tokens_within_budget": m["proposal"]["tokens_mean"] <= B["proposal_tokens"]}
    if "analysis_list_cost_usd" in B:
        res["verdict"]["analysis_cost_within_budget"] = m["analysis"]["list_cost_usd_mean"] <= B["analysis_list_cost_usd"]
        res["verdict"]["proposal_cost_within_budget"] = m["proposal"]["list_cost_usd_mean"] <= B["proposal_list_cost_usd"]
    (ROOT / "evals/results" / f"budget_run_{prof}.json").write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--analysis", type=int, default=8); ap.add_argument("--proposals", type=int, default=4); a = ap.parse_args()
    asyncio.run(main(a.analysis, a.proposals))
