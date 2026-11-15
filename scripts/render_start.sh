#!/usr/bin/env bash
# Entry point of the Render container. Secrets arrive as environment variables set in the Render dashboard; nothing is read from a file.
set -euo pipefail
cd /app
python -m uvicorn gigsim.app:app --host 127.0.0.1 --port 8081 &
sleep 2
python scripts/seed_reviewer.py || echo "reviewer seed failed (continuing)"
exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port "${PORT:-10000}"
