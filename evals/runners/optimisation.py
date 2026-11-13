"""E5: optimisations that helped, measured without any LLM (CPU only, reproducible).
 (1) Fit Matcher: one retrieval per requirement issued concurrently vs sequentially (same results, lower latency).
 (2) Prompt trimming: writer/verifier evidence limited to 6 items x 600 chars (was every item x 900 chars): prompt size in estimated tokens.
Writes evals/results/optimisation.json.   Run: python -m evals.runners.optimisation --n 12"""
from __future__ import annotations

import argparse
import asyncio
import json
import time

from agent.nodes import analyst, fit_matcher
from agent.tools import LocalToolbox
from evals.runners.common import marketplace, pct
from evals.runners.rag_eval import ROOT, load_jobs


async def main(n):
    tb = LocalToolbox("ai_ml", marketplace())
    jobs = [j for j in load_jobs("ai_ml") if j["kind"] == "good"][:n]
    await fit_matcher.match(tb, analyst.deterministic_spec(jobs[0]))             # warm-up (model load) excluded from timings
    seq, con, same = [], [], 0
    evid = []
    for j in jobs:
        spec = analyst.deterministic_spec(j)
        t = time.perf_counter(); a, ev = await fit_matcher.match(tb, spec, concurrent=False); seq.append(time.perf_counter() - t)
        t = time.perf_counter(); b, _ = await fit_matcher.match(tb, spec, concurrent=True); con.append(time.perf_counter() - t)
        same += a.model_dump() == b.model_dump(); evid.append(ev)
    full = sum(sum(len(e["text"]) for e in ev) for ev in evid) / len(evid)
    trimmed = sum(sum(len(e["text"][:600]) for e in ev[:6]) for ev in evid) / len(evid)
    out = {"n_jobs": len(jobs), "fit_matcher": {"sequential_p50_s": pct(seq, .5), "concurrent_p50_s": pct(con, .5), "sequential_p95_s": pct(seq, .95), "concurrent_p95_s": pct(con, .95),
                                               "speedup_p50": round(pct(seq, .5) / pct(con, .5), 2), "identical_output_rate": same / len(jobs),
                                               "note": "CPU-bound retrieval on a 4-core laptop: speedup is limited by the cores/GIL; with the MCP portfolio server it also overlaps IPC"},
           "prompt_trimming": {"evidence_chars_per_prompt_before": round(full), "after": round(trimmed), "estimated_tokens_before": round(full / 3), "after_tokens": round(trimmed / 3),
                               "reduction_pct": round(100 * (1 - trimmed / full), 1), "applies_to": "writer prompt (every revision) and verifier prompt (2 calls per revision)"}}
    (ROOT / "evals/results/optimisation.json").write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=12); a = ap.parse_args(); asyncio.run(main(a.n))
