"""Run the full evaluation suite SEQUENTIALLY (the free-tier LLM limits are per model, so parallel runs would collide).
Each step writes its own evals/results/*.json; a failed step is logged and the suite continues.
Sizes are set by what the free tier allows (8000 tokens/min/model); see docs/DATA_CARD.md and the report for the consequences."""
import subprocess, sys, time

STEPS = [
    ("rag variants", [sys.executable, "-m", "evals.runners.rag_eval", "--n", "60"]),
    ("rag ablation", [sys.executable, "-m", "evals.runners.ablation"]),
    ("decision, config A", [sys.executable, "-m", "evals.runners.decision_eval", "--n", "20", "--configs", "A"]),
    ("tool granularity (R&D A)", [sys.executable, "-m", "evals.runners.tool_granularity"]),
    ("proposals V0 vs V3", [sys.executable, "-m", "evals.runners.proposal_eval", "--variants", "v0_naive", "v3_rerank", "--n", "8"]),
    ("injection defence", [sys.executable, "-m", "evals.runners.injection_eval", "--n", "8"]),
    ("architecture comparison (R&D C)", [sys.executable, "-m", "evals.runners.arch_compare", "--n", "16"]),
]

if __name__ == "__main__":
    only = sys.argv[1:]
    for name, cmd in STEPS:
        if only and not any(o in name for o in only):
            continue
        t = time.time(); print(f"\n=== {name}", flush=True)
        rc = subprocess.call(cmd)
        print(f"=== {name}: exit {rc} in {time.time() - t:.0f}s", flush=True)
