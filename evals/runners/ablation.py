"""Ablate the best composed pipeline one component at a time (R&D question B). Writes evals/results/rag_ablation.json."""
from __future__ import annotations

import json
from functools import partial

from evals.runners.rag_eval import PERSONAS, ROOT, evaluate, load_jobs
from rag.index.store import Index
from rag.ingest.loaders import load_persona
from rag.variants.pipeline import retrieve_flags

FULL = dict(decompose=True, sparse=True, rerank=True, outcome=True)


def main(n: int = 60):
    out = {"base": "all components on (decompose + BM25 + rerank + outcome)", "n_per_persona": n, "runs": {}}
    configs = {"full": FULL, **{f"minus_{c}": {**FULL, c: False} for c in FULL}}
    for persona in PERSONAS:
        idx, jobs = Index(load_persona(persona)), load_jobs(persona, n)
        for name, flags in configs.items():
            r = evaluate(partial(retrieve_flags, **flags), idx, jobs)
            out["runs"].setdefault(name, {})[persona] = r
            print(f"{persona:13s} {name:16s} R@5={r['recall@5']} MRR={r['mrr']} nDCG={r['ndcg@10']}", flush=True)
    for name, per in out["runs"].items():
        out["runs"][name]["macro"] = {m: round(sum(per[p][m] for p in PERSONAS) / 3, 4) for m in ("recall@5", "mrr", "ndcg@10")}
    (ROOT / "evals/results/rag_ablation.json").write_text(json.dumps(out, indent=2)); print("wrote rag_ablation.json")


if __name__ == "__main__":
    main()
