"""R&D question C: is the multi-agent design worth it?
Same dev jobs, three architectures: (a) ONE ReAct agent holding all read tools, (b) the prebuilt `langgraph-supervisor`
(supervisor + analyst + writer workers), (c) our hand-built graph. (a)/(b) use the strong model everywhere; (c) routes cheap nodes
to the small model as shipped. Metrics: bid-or-skip accuracy, unsupported claims, policy violations in the raw output (what the
Compliance Guard would have to catch), GigSim reply rate, tokens/cost, latency, broken down by job type.
Run: python -m evals.runners.arch_compare --n 50"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import uuid

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from langgraph_supervisor import create_supervisor

from agent import llm as L
from agent.graphs.bid_graph import build_bid_graph
from agent.nodes import compliance
from agent.prompts import load_prompt
from agent.tools import LocalToolbox
from evals.runners.common import gather_limited, marketplace, pct
from evals.runners.rag_eval import ROOT, load_jobs
from rag import verify as ver

PERSONA = "ai_ml"
TASK = load_prompt("baseline_single_agent")


def make_llm(tier="strong"):
    import httpx
    r = L.resolve("writer" if tier == "strong" else "scout")
    limit = L.load_config()["models"]["rate_limits"]["tokens_per_minute"]

    async def throttle(request):                                   # same client-side TPM limiter as agent/llm.py, async-safe
        est = len(request.content) // 3 + 1500                      # prompt + generous allowance for hidden reasoning tokens
        while (w := L.THROTTLE.wait_time(r["model"], est, limit)) > 0:
            await asyncio.sleep(w)
    return ChatOpenAI(model=r["model"], base_url=r["base_url"], api_key=os.environ[r["key_env"]], temperature=0.2, timeout=120, max_retries=4,
                      http_async_client=httpx.AsyncClient(event_hooks={"request": [throttle]}, timeout=120))


def lc_tools(tb, names):
    @tool
    async def search_evidence(requirement: str, k: int = 3) -> str:
        """Find portfolio evidence (projects) that proves one requirement or skill. Call once per requirement."""
        return json.dumps(await tb.call("single_agent", "search_evidence", requirement=requirement, k=k))

    @tool
    async def get_client_history(client_id: str) -> str:
        """Get a client's public history: spend, rating, hire rate, payment verification."""
        return json.dumps(await tb.call("single_agent", "get_client_history", client_id=client_id))

    @tool
    async def get_market_stats(category: str) -> str:
        """Market price percentiles (fixed and hourly USD) for ai_ml, fullstack or data_analyst jobs."""
        return json.dumps(await tb.call("single_agent", "get_market_stats", category=category))

    @tool
    async def list_skills() -> str:
        """List the skills in the freelancer's portfolio."""
        return json.dumps(await tb.call("single_agent", "list_skills"))

    all_ = {"search_evidence": search_evidence, "get_client_history": get_client_history, "get_market_stats": get_market_stats, "list_skills": list_skills}
    return [all_[n] for n in names]


def parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def job_prompt(job):
    return f"{TASK}\n\nJOB (client_id={job['client_id']}, category={PERSONA}, connects={job['connects_cost']}):\n<untrusted_job_post>\n{job['title']}\n{job['description']}\nRequired skills: {job['required_skills']}\nBudget: {job['budget']}\n</untrusted_job_post>"


async def run_single(tb, job):
    agent = create_react_agent(make_llm(), lc_tools(tb, ["search_evidence", "get_client_history", "get_market_stats", "list_skills"]))
    cb = UsageMetadataCallbackHandler()
    out = await agent.ainvoke({"messages": [("user", job_prompt(job))]}, {"callbacks": [cb], "recursion_limit": 30})
    return parse(out["messages"][-1].content), cb.usage_metadata


async def run_supervisor(tb, job):
    m = make_llm()
    analyst = create_react_agent(m, lc_tools(tb, ["get_client_history", "get_market_stats", "search_evidence"]), name="analyst_agent",
                                 prompt=load_prompt("baseline_analyst_worker"))
    writer = create_react_agent(m, lc_tools(tb, ["search_evidence"]), name="writer_agent",
                                prompt=load_prompt("baseline_writer_worker"))
    sup = create_supervisor([analyst, writer], model=m, prompt=load_prompt("baseline_supervisor")).compile()
    cb = UsageMetadataCallbackHandler()
    out = await sup.ainvoke({"messages": [("user", job_prompt(job))]}, {"callbacks": [cb], "recursion_limit": 40})
    return parse(out["messages"][-1].content), cb.usage_metadata


async def run_graph(tb, job):
    g = build_bid_graph(tb, InMemoryStore(), MemorySaver())
    cfg = {"configurable": {"thread_id": uuid.uuid4().hex}}
    usage = []
    tok = L.USAGE.set(usage)
    try:
        out = await g.ainvoke({"job": job, "user_id": "arch-graph", "persona": PERSONA, "settings": {"floor_hourly": 30}}, cfg)
        st = await g.aget_state(cfg)
        if st.next == ("approval",):
            final = await g.ainvoke(Command(resume={"action": "approve"}), cfg)
            return {"decision": "bid", "cover_letter": final["send_text"], "bid_amount": out["price_quote"]["amount"], "violations_caught": out["compliance"]["violations"],
                    "evidence": out["evidence"], "unsupported": out.get("unsupported_after")}, {"graph": {"input_tokens": sum(u[1] for u in usage), "output_tokens": sum(u[2] for u in usage), "cost": sum(L.cost_usd(*u) for u in usage)}}
        return {"decision": "skip", "reason": out["decision"]["reason"]}, {"graph": {"input_tokens": sum(u[1] for u in usage), "output_tokens": sum(u[2] for u in usage), "cost": sum(L.cost_usd(*u) for u in usage)}}
    finally:
        L.USAGE.reset(tok)


def cost_of(usage: dict) -> tuple[int, float]:
    toks = sum(v.get("input_tokens", 0) + v.get("output_tokens", 0) for v in usage.values())
    c = sum(v["cost"] if "cost" in v else L.cost_usd(m, v.get("input_tokens", 0), v.get("output_tokens", 0)) for m, v in usage.items())
    return toks, c


async def evaluate_arch(name, runner, jobs, tb_for_user, shared_tb):
    async def one(job):
        t0 = time.time()
        res, usage = await runner(shared_tb, job)
        lat = time.time() - t0
        toks, cost = cost_of(usage)
        dec = str(res.get("decision", "")).lower()
        row = {"job_id": job["job_id"], "kind": job["kind"], "pred": dec if dec in ("bid", "skip") else "skip", "gold": job["gold"]["decision"], "latency_s": lat, "tokens": toks, "cost": cost}
        if dec == "bid" and res.get("cover_letter"):
            text = compliance.strip_citations(res["cover_letter"]) if name != "hand_graph" else res["cover_letter"]
            raw_viol = compliance.check(compliance.strip_citations(res["cover_letter"]).ljust(150)).violations
            row["raw_policy_violations"] = [v for v in raw_viol if v != "length_out_of_bounds"]
            ev = res.get("evidence") or await shared_tb.call("single_agent", "search_evidence", requirement=", ".join(job["required_skills"]), k=4)
            claims = await asyncio.to_thread(ver.verify_claims, text, ev)
            row["unsupported_rate"] = ver.unsupported_rate(claims)
            mp = tb_for_user(name)
            try:
                d = await mp.create_proposal_draft({"job_id": job["job_id"], "cover_letter": (text.ljust(160, " ") if len(text) < 150 else text[:3000]), "bid_amount": float(res.get("bid_amount") or 500)}, uuid.uuid4().hex)
                sub = await mp.submit_proposal(d["proposal_id"], uuid.uuid4().hex)
                row["outcome"] = sub.get("outcome")
            except Exception as e:  # noqa: BLE001
                row["submit_error"] = str(e)[:80]
        return row
    res = await gather_limited([one(j) for j in jobs], limit=4)
    return [r for r in res if isinstance(r, dict)], [str(r)[:120] for r in res if isinstance(r, Exception)]


def summarise(rows):
    n = len(rows); bids = [r for r in rows if r["pred"] == "bid" and "unsupported_rate" in r]
    acc = sum(r["pred"] == r["gold"] for r in rows) / n
    by = {}
    for k in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == k]; by[k] = {"n": len(sub), "decision_accuracy": round(sum(r["pred"] == r["gold"] for r in sub) / len(sub), 3)}
    sent = [r for r in bids if r.get("outcome")]
    return {"n_jobs": n, "decision_accuracy": round(acc, 3), "by_job_type": by, "n_proposals": len(bids),
            "unsupported_claim_rate_mean": round(sum(r["unsupported_rate"] for r in bids) / len(bids), 3) if bids else None,
            "proposals_with_raw_policy_violation": round(sum(1 for r in bids if r["raw_policy_violations"]) / len(bids), 3) if bids else None,
            "gigsim_reply_rate": round(sum(r["outcome"] in ("reply", "interview", "hire") for r in sent) / len(sent), 3) if sent else None, "n_sent": len(sent),
            "p50_latency_s": pct([r["latency_s"] for r in rows], .5), "p95_latency_s": pct([r["latency_s"] for r in rows], .95),
            "tokens_per_job": round(sum(r["tokens"] for r in rows) / n), "list_cost_usd_per_job": round(sum(r["cost"] for r in rows) / n, 5)}


async def main(n):
    jobs = load_jobs(PERSONA, n)
    shared = LocalToolbox(PERSONA, marketplace("arch-shared"))
    users = {}
    def mp(name):
        return users.setdefault(name, marketplace(f"arch-{name}"))
    out = {"persona": PERSONA, "n_jobs": len(jobs), "note": "(a)/(b) use the strong model for every step; (c) uses shipped per-node routing. (a)/(b) have NO Compliance Guard, so 'raw policy violations' = what reached the output.", "architectures": {}}
    for name, runner in [("hand_graph", run_graph), ("single_react_agent", run_single), ("prebuilt_supervisor", run_supervisor)]:
        rows, errs = await evaluate_arch(name, runner, jobs, mp, shared)
        out["architectures"][name] = summarise(rows) | {"errors": errs[:3], "n_errors": len(errs)}
        (ROOT / "evals/results" / f"arch_rows_{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        print(name, json.dumps({k: v for k, v in out["architectures"][name].items() if k not in ("by_job_type",)}), flush=True)
    (ROOT / "evals/results/arch_compare.json").write_text(json.dumps(out, indent=2)); print("wrote arch_compare.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=50); a = ap.parse_args(); asyncio.run(main(a.n))
