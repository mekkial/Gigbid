#!/usr/bin/env bash
# Entry point of the Hugging Face Space container. Secrets arrive as environment variables (Space secrets); nothing is read from a file.
set -euo pipefail
cd /app
python -m uvicorn gigsim.app:app --host 127.0.0.1 --port 8081 &
sleep 2
MCP_HOST=127.0.0.1 MARKETPLACE_MCP_PORT=8082 python -m mcp_servers.marketplace.server &
python scripts/seed_reviewer.py || echo "seed failed (continuing)"
exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 7860
