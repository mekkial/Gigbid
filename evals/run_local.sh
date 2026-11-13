#!/usr/bin/env bash
# Local-model evaluation chain (Ollama qwen3:8b, no quota). One step at a time; a failed step does not stop the chain.
cd "$(dirname "$0")/.."
export MODEL_PROFILE=local
PY=.venv/bin/python
step() { echo "=== $1"; shift; "$@"; echo "=== exit $?"; }
step "decision A@local"        $PY -m evals.runners.decision_eval --n 12 --configs A
step "proposals V0 vs V3"      $PY -m evals.runners.proposal_eval --variants v0_naive v3_rerank --n 6
step "injection defence"       $PY -m evals.runners.injection_eval --n 6
step "budget run (local)"      $PY -m evals.runners.budget_run --analysis 8 --proposals 3
step "architecture comparison" $PY -m evals.runners.arch_compare --n 10
echo "=== CHAIN DONE"
