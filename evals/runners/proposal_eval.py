"""System-level proposal eval (B3/B4/B5): runs the FULL bid graph per retrieval variant on a fixed, paired job set; a simulated human
approves each draft unchanged; the proposal is submitted to GigSim, whose hidden-preference clients decide ignore/reply/interview/hire.
Reports: unsupported claims before/after verification (LLM verifier AND an independent deterministic number-grounding check), judge score,
GigSim reply/hire rate (+95% CI), p50/p95 latency, tokens, list-price USD per proposal.
Run: python -m evals.runners.proposal_eval --variants v0_naive v3_rerank --n 12"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from agent.tools import LocalToolbox
from evals.judge import judge
from evals.runners.common import gather_limited, marketplace, pct
from evals.runners.rag_eval import PERSONAS, ROOT, load_jobs
from rag.index.store import Index
from rag.ingest.loaders import load_persona
from rag.retriever import get_retriever

NUM = re.compile(r"\d+(?:\.\d+)?")


def ungrounded_numbers(text: str, evidence: list[dict], job: dict, price: float) -> int:
    """Independent of any LLM: numbers in the proposal that appear in no evidence, job post or bid are fabricated."""
    ok = set(NUM.findall(" ".join(e["text"] for e in evidence) + " " + job["title"] + " " + job["description"] + f" {price:g}"))
    return sum(1 for n in NUM.findall(text) if n not in ok)


def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def two_prop_p(k1, n1, k2, n2):
    if not n1 or not n2: return None
    p = (k1 + k2) / (n1 + n2); se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = abs(k1 / n1 - k2 / n2) / se
    return round(math.erfc(z / math.sqrt(2)), 4)


async def run_one(graph, job, persona, user):
    cfg = {"configurable": {"thread_id": f"pe-{uuid.uuid4().hex[:8]}"}}
    inp = {"job": job, "user_id": user, "persona": persona, "settings": {"floor_hourly": 30}}
    out = await graph.ainvoke(inp, cfg)
    st = await graph.aget_state(cfg)
    if st.next != ("approval",):
        return {"status": out.get("status"), "job_id": job["job_id"]}
    final = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
    send = final["send_text"]; ev = out["evidence"]
    verdict = await asyncio.to_thread(judge, job, send, ev)
    t = out["trace"]
    return {"status": final["status"], "job_id": job["job_id"], "outcome": (final.get("outcome") or {}).get("outcome"), "text": send,
            "unsupported_before": out.get("unsupported_before"), "unsupported_after": out.get("unsupported_after"),
            "ungrounded_numbers": ungrounded_numbers(send, ev, job, out["price_quote"]["amount"]),
            "judge": verdict.model_dump(), "latency_s": round(sum(x["latency_s"] for x in t), 2), "tokens": out.get("tokens"),
            "cost_usd": out.get("cost_usd"), "revisions": out.get("revision")}


async def run_variant(variant, jobs_by_persona, indexes):
    rows = []
    for persona, jobs in jobs_by_persona.items():
        tb = LocalToolbox(persona, marketplace(f"eval-{variant}"), index=indexes[persona], retrieve=get_retriever(variant))
        g = build_bid_graph(tb, InMemoryStore(), MemorySaver())
        res = await gather_limited([run_one(g, j, persona, f"eval-{variant}") for j in jobs], limit=2)
        rows += [{"persona": persona, **r} for r in res if isinstance(r, dict)]
        errs = [r for r in res if isinstance(r, Exception)]
        print(variant, persona, f"{len(res) - len(errs)} ok, {len(errs)} errors", [str(e)[:80] for e in errs[:2]], flush=True)
    return rows


def summarise(rows):
    done = [r for r in rows if r.get("text")]
    n = len(done)
    if not n: return {"n": 0}
    replies = sum(r["outcome"] in ("reply", "interview", "hire") for r in done); hires = sum(r["outcome"] == "hire" for r in done)
    lat = [r["latency_s"] for r in done]
    return {"n_proposals": n, "reply_rate": round(replies / n, 3), "reply_ci95": wilson(replies, n), "hire_rate": round(hires / n, 3), "hire_ci95": wilson(hires, n),
            "unsupported_claims_per_proposal_before": round(sum(r["unsupported_before"] or 0 for r in done) / n, 3),
            "unsupported_rate_before_verification": round(sum(1 for r in done if (r["unsupported_before"] or 0) > 0) / n, 3),
            "unsupported_rate_after_verification": round(sum(1 for r in done if (r["unsupported_after"] or 0) > 0) / n, 3),
            "ungrounded_numbers_per_proposal": round(sum(r["ungrounded_numbers"] for r in done) / n, 3),
            "judge_overall_mean": round(sum(r["judge"]["overall"] for r in done) / n, 3), "judge_acceptable_rate": round(sum(r["judge"]["acceptable"] for r in done) / n, 3),
            "p50_latency_s": pct(lat, .5), "p95_latency_s": pct(lat, .95), "tokens_per_proposal": round(sum(r["tokens"] or 0 for r in done) / n),
            "list_cost_usd_per_proposal": round(sum(r["cost_usd"] or 0 for r in done) / n, 6), "avg_revisions": round(sum(r["revisions"] or 0 for r in done) / n, 2),
            "_counts": {"replies": replies, "hires": hires, "n": n}}


async def main(variants, n, out_name):
    jobs = {p: [j for j in load_jobs(p) if j["kind"] == "good"][:n] for p in PERSONAS}
    idx = {p: Index(load_persona(p)) for p in PERSONAS}
    from agent.llm import active_profile_info
    res = {"llm": active_profile_info(), "jobs_per_persona": n, "note": "simulated human approves each draft unchanged; judge = qwen3.8-27b (uncalibrated until judge_calibration.py is run with human labels)", "variants": {}}
    for v in variants:
        rows = await run_variant(v, jobs, idx)
        res["variants"][v] = {"overall": summarise(rows), "by_persona": {p: summarise([r for r in rows if r["persona"] == p]) for p in PERSONAS}}
        (ROOT / "evals/results" / f"proposals_{v}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        print(v, json.dumps(res["variants"][v]["overall"]), flush=True)
    vs = list(res["variants"])
    if len(vs) >= 2 and all("_counts" in res["variants"][v]["overall"] for v in vs[:2]):
        a, b = res["variants"][vs[0]]["overall"]["_counts"], res["variants"][vs[1]]["overall"]["_counts"]
        res["reply_rate_diff_p_value_two_proportion"] = {f"{vs[0]}_vs_{vs[1]}": two_prop_p(a["replies"], a["n"], b["replies"], b["n"])}
    (ROOT / "evals/results" / out_name).write_text(json.dumps(res, indent=2)); print("wrote", out_name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--variants", nargs="+", default=["v0_naive", "v3_rerank"]); ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out", default="proposal_eval.json"); a = ap.parse_args(); asyncio.run(main(a.variants, a.n, a.out))
