"""Calibrate V8's abstention threshold WITHOUT tuning on the test data: pick the cross-encoder threshold on ONE persona (ai_ml),
evaluate on the other two. Score = best cross-encoder logit of the top retrieved evidence for the job.
Goal: abstain on jobs that should be skipped (no gold evidence) while not abstaining on good jobs. Writes evals/results/v8_threshold.json."""
import json

import numpy as np

from evals.runners.rag_eval import PERSONAS, ROOT, load_jobs
from rag.index.store import Index
from rag.ingest.loaders import load_persona
from rag.retriever import job_query
from rag.variants.pipeline import rerank_scores, retrieve_flags


def top_scores(persona, n=60):
    idx, jobs = Index(load_persona(persona)), load_jobs(persona, n)
    rows = []
    for j in jobs:
        q = job_query(j)
        cands = retrieve_flags(q, idx, 30, sparse=True, rerank=True)
        pos = {c["chunk_id"]: i for i, c in enumerate(idx.chunks)}
        s = rerank_scores(idx, q, [pos[c["chunk_id"]] for c in cands])
        rows.append({"kind": j["kind"], "has_gold": bool(j["gold"]["evidence_ids"]), "top": max(s) if s else -99, "should_skip": j["kind"] == "skip"})
    return rows


def rates(rows, thr):
    skip = [r for r in rows if r["should_skip"]]; good = [r for r in rows if r["has_gold"]]
    return {"abstain_on_skip": round(float(np.mean([r["top"] <= thr for r in skip])), 3), "false_abstain_on_gold_jobs": round(float(np.mean([r["top"] <= thr for r in good])), 3), "n_skip": len(skip), "n_gold": len(good)}


def main():
    data = {p: top_scores(p) for p in PERSONAS}
    cal = data["ai_ml"]
    cands = sorted({round(r["top"], 2) for r in cal})
    best = max(cands, key=lambda t: (rates(cal, t)["abstain_on_skip"] - rates(cal, t)["false_abstain_on_gold_jobs"], -abs(t)))
    out = {"calibrated_on": "ai_ml", "threshold": best, "calibration_rates": rates(cal, best),
           "held_out": {p: rates(data[p], best) for p in PERSONAS if p != "ai_ml"},
           "default_threshold_0.0": {p: rates(data[p], 0.0) for p in PERSONAS},
           "score_summary": {p: {"top_logit_mean_gold": round(float(np.mean([r["top"] for r in data[p] if r["has_gold"]])), 2),
                                 "top_logit_mean_skip": round(float(np.mean([r["top"] for r in data[p] if r["should_skip"]])), 2)} for p in PERSONAS}}
    (ROOT / "evals/results/v8_threshold.json").write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
