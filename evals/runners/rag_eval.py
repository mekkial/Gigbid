"""Retrieval eval (B4): evidence Recall@5, MRR, nDCG@10 vs gold evidence projects; per persona and per job type;
abstention behaviour for jobs that should be skipped; latency. Writes evals/results/rag_eval.json.
Run: python -m evals.runners.rag_eval [--n 60] [--variants ...]   (n = jobs per persona, stratified, seeded)"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path

from rag.index.store import Index
from rag.ingest.loaders import load_persona
from rag.retriever import VARIANTS, get_retriever, job_query

ROOT = Path(__file__).resolve().parents[2]
PERSONAS = ["ai_ml", "fullstack", "data_analyst"]
SEED = 4016


def kind_of(j: dict) -> str:
    g = j["gold"]
    return "scam" if g["scam"] else "injection" if g["injected"] else "lowball" if j["budget"]["max"] <= 20 \
        else "skip" if g["decision"] == "skip" else "good"


def load_jobs(persona: str, n: int = 0) -> list[dict]:
    jobs = [json.loads(l) for l in (ROOT / "evals/datasets" / f"dev_{persona}.jsonl").read_text().splitlines()]
    jobs = [j for j in jobs if "duplicate_of" not in j]
    for j in jobs:
        j["kind"] = kind_of(j)
    if n:                                                        # stratified, seeded subsample
        rng, by = random.Random(SEED), defaultdict(list)
        for j in jobs: by[j["kind"]].append(j)
        out = []
        for k, v in by.items():
            rng.shuffle(v); out += v[: max(1, round(n * len(v) / len(jobs)))]
        jobs = out
    return jobs


def ranked_projects(chunks: list[dict]) -> list[str]:
    return list(dict.fromkeys(c["project"].removesuffix("-v2") for c in chunks if c["project"] != "cv"))


def metrics(ranked: list[str], gold: set[str]) -> dict:
    gold = {g.removesuffix("-v2") for g in gold}
    r5 = len(set(ranked[:5]) & gold) / len(gold)
    mrr = next((1 / (i + 1) for i, p in enumerate(ranked) if p in gold), 0.0)
    dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(ranked[:10]) if p in gold)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    return {"recall@5": r5, "mrr": mrr, "ndcg@10": dcg / idcg if idcg else 0.0}


def mean(rows, key):
    return round(sum(r[key] for r in rows) / len(rows), 4) if rows else None


def pct(xs, p):
    xs = sorted(xs); return round(xs[min(len(xs) - 1, int(len(xs) * p))], 4) if xs else None


def evaluate(fn, idx, jobs) -> dict:
    """fn(query, index, k) -> chunks. Returns aggregate + per-job-type breakdown."""
    rows, lat, abst = [], [], []
    for j in jobs:
        t = time.time(); chunks = fn(job_query(j), idx, k=30); lat.append(time.time() - t)
        ranked = ranked_projects(chunks)
        if j["gold"]["evidence_ids"]:
            rows.append(metrics(ranked, set(j["gold"]["evidence_ids"])) | {"kind": j["kind"], "abstained": not ranked})
        elif j["kind"] == "skip":
            abst.append(not ranked)
    agg = {m: mean(rows, m) for m in ("recall@5", "mrr", "ndcg@10")}
    agg["by_job_type"] = {k: {m: mean([r for r in rows if r["kind"] == k], m) for m in ("recall@5", "mrr", "ndcg@10")} | {"n": sum(r["kind"] == k for r in rows)} for k in sorted({r["kind"] for r in rows})}
    agg |= {"n_scored": len(rows), "false_abstain_rate": round(sum(r["abstained"] for r in rows) / len(rows), 4) if rows else None,
            "abstain_rate_on_skip_jobs": round(sum(abst) / len(abst), 4) if abst else None, "n_skip_jobs": len(abst),
            "p50_s": pct(lat, .5), "p95_s": pct(lat, .95)}
    return agg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--n", type=int, default=60); ap.add_argument("--out", default="rag_eval.json"); ap.add_argument("--merge", action="store_true", help="update only the listed variants inside an existing results file"); a = ap.parse_args()
    results: dict = {"config": {"n_per_persona": a.n, "seed": SEED, "corpus": "synthetic personas (see docs/DATA_CARD.md)"}, "variants": {}}
    for persona in PERSONAS:
        idx, jobs = Index(load_persona(persona)), load_jobs(persona, a.n)
        for v in a.variants:
            res = evaluate(get_retriever(v), idx, jobs)
            results["variants"].setdefault(v, {})[persona] = res
            print(f"{persona:13s} {v:14s} R@5={res['recall@5']} MRR={res['mrr']} nDCG={res['ndcg@10']} abst(skip)={res['abstain_rate_on_skip_jobs']} p95={res['p95_s']}s", flush=True)
    if a.merge and (ROOT / "evals/results" / a.out).exists():
        old = json.loads((ROOT / "evals/results" / a.out).read_text()); old["variants"].update(results["variants"]); results = old
    for v, per in results["variants"].items():                    # macro average over personas
        results["variants"][v]["macro"] = {m: round(sum(per[p][m] for p in PERSONAS) / 3, 4) for m in ("recall@5", "mrr", "ndcg@10", "p95_s")}
    (ROOT / "evals/results" / a.out).write_text(json.dumps(results, indent=2)); print("wrote", a.out)


if __name__ == "__main__":
    main()
