"""30-job smoke eval for CI (E2): decision metrics on 30 jobs (10 per persona) + unsupported-claim rate on 6 generated proposals.
Writes evals/results/smoke.json, which evals/check_thresholds.py gates on."""
import asyncio
import json

from evals.runners import decision_eval, proposal_eval
from evals.runners.rag_eval import PERSONAS, ROOT, load_jobs
from rag.index.store import Index
from rag.ingest.loaders import load_persona


async def main():
    per = {}
    for p in PERSONAS:                                            # one pass per persona (token-limited free tier: no repeats)
        per[p] = await decision_eval.run_persona(p, 10, "A")
    mean = lambda key, m: sum(per[p][key][m] for p in PERSONAS) / len(PERSONAS)  # noqa: E731
    jobs = {p: [j for j in load_jobs(p) if j["kind"] == "good"][:2] for p in PERSONAS}
    idx = {p: Index(load_persona(p)) for p in PERSONAS}
    rows = await proposal_eval.run_variant("v3_rerank", jobs, idx)
    s = proposal_eval.summarise(rows)
    out = {"n_jobs": 30, "bid_or_skip": {"f1": round(mean("bid_or_skip", "f1"), 4)},
           "scam": {"recall": round(mean("scam", "recall"), 4), "precision": round(mean("scam", "precision"), 4)},
           "unsupported_rate_after_verification": s.get("unsupported_rate_after_verification"), "n_proposals": s.get("n_proposals"),
           "per_persona": per}
    (ROOT / "evals/results/smoke.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "per_persona"}))


if __name__ == "__main__":
    asyncio.run(main())
