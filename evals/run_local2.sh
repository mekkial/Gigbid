#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export MODEL_PROFILE=local
PY=.venv/bin/python
echo "=== architecture comparison (fixed accounting + parse tracking)"; $PY -m evals.runners.arch_compare --n 10; echo "=== exit $?"
echo "=== injection defence (strict metric)"; $PY -m evals.runners.injection_eval --n 6; echo "=== exit $?"
echo "=== CHAIN2 DONE"
