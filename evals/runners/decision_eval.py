"""Decision eval (B4/C): bid-or-skip F1, scam precision/recall, injection detection, price inside the fair band, latency, tokens, cost.
Uses the REAL analyst / risk / fit / pricing nodes and the shared decision rule. Compares open-model configurations (A/B/C).
Run: python -m evals.runners.decision_eval --n 40 --configs A B C"""
from __future__ import annotations

import argparse
import asyncio
import json

from evals.runners.common import f1, gather_limited, marketplace, model_config, pct, tracked
from evals.runners.rag_eval import PERSONAS, ROOT, load_jobs
from agent.nodes import analyst, fit_matcher, pricing, risk_assessor
from agent.nodes.decision import decide
from agent.tools import LocalToolbox

CONFIGS = {"A": {}, "B": {"small": "qwen/qwen3.8-27b"}, "C": {"small": "openai/gpt-oss-120b"}}      # A = shipped default (small=gpt-oss-20b)


async def analyse_job(tb, job, floor):
    spec = await asyncio.to_thread(analyst.analyse, job)
    risk, (fit, _) = await asyncio.gather(risk_assessor.assess(tb, job), fit_matcher.match(tb, spec))
    d = decide(risk, fit, None, job, floor)
    price = await pricing.quote(tb, spec, fit, risk, floor, job["connects_cost"]) if d.action == "bid" else None
    return {"action": d.action, "scam": risk.is_scam, "inj": risk.injection_detected, "price": price.amount if price else None, "fit": fit.score, "risk": risk.score}


async def run_persona(persona, n, config, floor=30):
    tb = LocalToolbox(persona, marketplace())
    jobs = load_jobs(persona, n)
    outs = await gather_limited([tracked(analyse_job, tb, j, floor) for j in jobs], limit=6)
    tp = fp = fn = stp = sfp = sfn = itp = ifn = inband = nbid = 0; lat, toks, cost, errors = [], [], [], 0
    for j, o in zip(jobs, outs):
        if isinstance(o, Exception):
            errors += 1; continue
        r, l, t, c = o; lat.append(l); toks.append(t); cost.append(c)
        gold_bid = j["gold"]["decision"] == "bid"; pred_bid = r["action"] == "bid"
        tp += gold_bid and pred_bid; fp += (not gold_bid) and pred_bid; fn += gold_bid and not pred_bid
        gs_, ps_ = j["gold"]["scam"], r["scam"]
        stp += gs_ and ps_; sfp += (not gs_) and ps_; sfn += gs_ and not ps_
        if j["gold"]["injected"]:
            itp += r["inj"]; ifn += not r["inj"]
        if pred_bid and gold_bid:
            lo, hi = j["gold"]["fair_price_band"]; nbid += 1; inband += lo <= r["price"] <= hi
    n_ok = len(lat)
    return {"n": n_ok, "errors": errors, "bid_or_skip": f1(tp, fp, fn), "scam": f1(stp, sfp, sfn),
            "injection_detection_recall": round(itp / (itp + ifn), 4) if itp + ifn else None,
            "price_in_band": round(inband / nbid, 4) if nbid else None, "p50_latency_s": pct(lat, .5), "p95_latency_s": pct(lat, .95),
            "tokens_per_job": round(sum(toks) / n_ok) if n_ok else 0, "list_cost_usd_per_job": round(sum(cost) / n_ok, 6) if n_ok else 0}


async def main(n, configs):
    f = ROOT / "evals/results/decision_eval.json"
    out = json.loads(f.read_text()) if f.exists() else {"configs": {}}
    out.setdefault("configs", {})
    from agent.llm import active_profile, active_profile_info
    for name in configs:
        label = name if active_profile() == "open" else f"{name}@{active_profile()}"      # Groq and local results never overwrite each other
        with model_config(CONFIGS[name] if active_profile() == "open" else {}):
            out["configs"][label] = {"overrides": (CONFIGS[name] if active_profile() == "open" else None) or "shipped default", "llm": active_profile_info(), "n_per_persona": n, "personas": {}}
            for p in PERSONAS:
                r = await run_persona(p, n, name)
                out["configs"][label]["personas"][p] = r
                print(label, p, json.dumps({k: r[k] for k in ("bid_or_skip", "scam", "p95_latency_s", "errors")}), flush=True)
    f.write_text(json.dumps(out, indent=2)); print("wrote decision_eval.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--configs", nargs="+", default=["A"])
    a = ap.parse_args(); asyncio.run(main(a.n, a.configs))
