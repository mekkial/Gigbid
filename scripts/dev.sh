#!/usr/bin/env bash
# Start the whole stack locally. Postgres (DATABASE_URL) and Redis (REDIS_URL) must already be running; see docs/RUNBOOK.md.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
PY=.venv/bin/python
trap 'kill 0' EXIT
$PY -m uvicorn gigsim.app:app --port 8081 &
sleep 1
GIGSIM_BASE_URL=http://127.0.0.1:8081 $PY -m mcp_servers.marketplace.server &
$PY -m uvicorn apps.api.main:app --port 8000 &
.venv/bin/arq worker.settings.WorkerSettings &
(cd apps/web && npm run dev) &
wait
