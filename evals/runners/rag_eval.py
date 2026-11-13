"""Retrieval eval (B4): evidence Recall@5, MRR, nDCG@10 vs gold evidence projects, per persona.
Run: python -m evals.runners.rag_eval --variants v0_naive v2_hybrid v3_rerank"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from rag.index.store import Index
from rag.ingest.loaders import load_persona
from rag.retriever import VARIANTS, get_retriever, job_query

ROOT = Path(__file__).resolve().parents[2]


def ranked_projects(chunks: list[dict]) -> list[str]:
    seen, out = set(), []
    for c in chunks:
        if c["project"] not in seen and c["project"] != "cv":
            seen.add(c["project"]); out.append(c["project"].removesuffix("-v2"))
    return list(dict.fromkeys(out))


def metrics(ranked: list[str], gold: set[str]) -> dict:
    gold = {g.removesuffix("-v2") for g in gold}
    r5 = len(set(ranked[:5]) & gold) / len(gold)
    mrr = next((1 / (i + 1) for i, p in enumerate(ranked) if p in gold), 0.0)
    dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(ranked[:10]) if p in gold)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    return {"recall@5": r5, "mrr": mrr, "ndcg@10": dcg / idcg if idcg else 0.0}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
    results = {}
    for persona in ["ai_ml", "fullstack", "data_analyst"]:
        idx = Index(load_persona(persona))
        jobs = [json.loads(l) for l in (ROOT / "evals/datasets" / f"dev_{persona}.jsonl").read_text().splitlines()]
        jobs = [j for j in jobs if j["gold"]["evidence_ids"] and "duplicate_of" not in j]
        if a.limit: jobs = jobs[: a.limit]
        for v in a.variants:
            fn, rows, lat = get_retriever(v), [], []
            for j in jobs:
                t = time.time()
                # retrieve plenty of chunks, then collapse to projects (evidence items)
                ranked = ranked_projects(fn(job_query(j), idx, k=30))
                lat.append(time.time() - t)
                rows.append(metrics(ranked, set(j["gold"]["evidence_ids"])))
            agg = {m: round(sum(r[m] for r in rows) / len(rows), 4) for m in rows[0]}
            lat.sort(); agg |= {"n_jobs": len(rows), "p50_s": round(lat[len(lat) // 2], 4), "p95_s": round(lat[int(len(lat) * .95) - 1], 4)}
            results.setdefault(v, {})[persona] = agg
            print(persona, v, agg)
    out = ROOT / "evals/results/rag_eval.json"; out.write_text(json.dumps(results, indent=2)); print("wrote", out)


if __name__ == "__main__":
    main()
