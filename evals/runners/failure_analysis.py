"""Failure analysis (report section 8): run the DETERMINISTIC part of the pipeline (analyst fields, rule-based risk, retrieval-backed fit
matcher, pricing; no LLM, no tokens, exactly reproducible) over dev jobs, list every failure, and group it into the brief's taxonomy:
missed evidence / wrong skip / wrong bid / mispriced / injection / scam miss. Also measures the fix tried for the largest group
(budget-below-floor rule) by running the decision with and without it. LLM-dependent categories (unsupported claim, generic opening,
compliance miss) come from evals/results/proposal_eval.json instead.  Run: python -m evals.runners.failure_analysis --n 80"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict

from agent.nodes import analyst, fit_matcher, pricing, risk_assessor
from agent.nodes.decision import decide
from agent.tools import LocalToolbox
from evals.runners.common import marketplace
from evals.runners.rag_eval import PERSONAS, ROOT, load_jobs

FLOOR = 30


async def one(tb, job):
    spec = analyst.deterministic_spec(job)
    risk = await risk_assessor.assess(tb, job, use_llm=False)
    fit, ev = await fit_matcher.match(tb, spec)
    base = decide(risk, fit)                                         # without the budget-floor rule
    fixed = decide(risk, fit, None, job, FLOOR)                      # with it (shipped)
    price = None
    if fixed.action == "bid":
        price = (await pricing.quote(tb, spec, fit, risk, FLOOR, job["connects_cost"])).amount
    return {"job_id": job["job_id"], "kind": job["kind"], "gold": job["gold"], "base": base.action, "fixed": fixed.action, "fixed_reason": fixed.reason,
            "scam": risk.is_scam, "inj": risk.injection_detected, "flags": risk.flags, "fit": round(fit.score, 2), "missing": fit.missing_skills, "price": price,
            "risk": round(risk.score, 2), "title": job["title"][:70]}


def classify(r, which):
    pred, g = r[which], r["gold"]
    out = []
    if g["decision"] == "bid" and pred != "bid":
        out.append("missed_evidence" if r["fit"] < 0.6 and not r["scam"] else "wrong_skip")
    if g["decision"] == "skip" and pred == "bid":
        out.append("wrong_bid:" + ("lowball_budget" if r["kind"] == "lowball" else "out_of_scope_fit" if r["kind"] == "skip" else r["kind"]))
    if g["scam"] and not r["scam"]:
        out.append("scam_miss")
    if g["injected"] and not r["inj"]:
        out.append("injection_not_flagged")
    if g["injected"] and pred != "bid":
        out.append("injection_changed_decision")
    if pred == "bid" and g["decision"] == "bid" and r["price"] is not None:
        lo, hi = g["fair_price_band"]
        if not (lo <= r["price"] <= hi):
            out.append("mispriced")
    return out


async def main(n):
    rows = []
    for p in PERSONAS:
        tb = LocalToolbox(p, marketplace())
        jobs = load_jobs(p, n)
        res = await asyncio.gather(*[one(tb, j) for j in jobs])
        rows += [r | {"persona": p} for r in res]
        print(p, len(res), flush=True)
    out = {"n_jobs": len(rows), "note": "deterministic pipeline only (no LLM); 'base' = before the budget-floor rule, 'fixed' = shipped", "taxonomy": {}, "examples": {}}
    for which in ("base", "fixed"):
        c = Counter(); ex = defaultdict(list)
        for r in rows:
            for cat in classify(r, which):
                c[cat] += 1
                if len(ex[cat]) < 4: ex[cat].append({k: r[k] for k in ("persona", "job_id", "title", "fit", "risk", "flags", "missing", "price", which)})
        out["taxonomy"][which] = dict(c.most_common())
        if which == "fixed": out["examples"] = dict(ex)
        correct = sum(r[which] == r["gold"]["decision"] for r in rows)
        tp = sum(r[which] == "bid" and r["gold"]["decision"] == "bid" for r in rows); fp = sum(r[which] == "bid" and r["gold"]["decision"] == "skip" for r in rows); fn = sum(r[which] != "bid" and r["gold"]["decision"] == "bid" for r in rows)
        pr, rc = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
        out.setdefault("bid_or_skip", {})[which] = {"accuracy": round(correct / len(rows), 4), "precision": round(pr, 4), "recall": round(rc, 4), "f1": round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0}
    out["failed_jobs_total"] = {w: sum(1 for r in rows if classify(r, w)) for w in ("base", "fixed")}
    (ROOT / "evals/results/failure_analysis.json").write_text(json.dumps(out, indent=2)); print(json.dumps({k: out[k] for k in ("taxonomy", "bid_or_skip", "failed_jobs_total")}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=80); a = ap.parse_args(); asyncio.run(main(a.n))
