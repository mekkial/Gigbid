#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export MODEL_PROFILE=local
echo "=== smoke eval"; .venv/bin/python -m evals.runners.smoke_eval; echo "=== exit $?"
echo "=== threshold gate"; .venv/bin/python evals/check_thresholds.py; echo "=== exit $?"
echo "=== SMOKE DONE"
