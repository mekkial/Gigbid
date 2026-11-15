#!/usr/bin/env bash
# Measure the memory of the light (BM25-only, no PyTorch) deployment: starts GigSim, the marketplace MCP server and the API on spare ports,
# runs one scout + analysis through the API, and records the total resident memory of all processes (peak and final).
# usage: scripts/measure_light_memory.sh [tools: mcp|local]    (needs .env with DATABASE_URL and GROQ_API_KEY)
set -uo pipefail
cd "$(dirname "$0")/.."
TOOLS=${1:-mcp}
set -a; . ./.env; set +a
export MODEL_PROFILE=open RAG_VARIANT=v6_bm25 GIGBID_TOOLS=$TOOLS REDIS_URL= GIGSIM_BASE_URL=http://127.0.0.1:9081 MARKETPLACE_MCP_URL=http://127.0.0.1:9082/mcp MARKETPLACE_MCP_PORT=9082 MCP_LEDGER_PATH=/tmp/gb_light_ledger.sqlite
PY=${PY:-.venv/bin/python}
P2=0
$PY -m uvicorn gigsim.app:app --port 9081 >/tmp/light_gigsim.log 2>&1 & P1=$!
[ "$TOOLS" = mcp ] && { $PY -m mcp_servers.marketplace.server >/tmp/light_mcp.log 2>&1 & P2=$!; }
sleep 3
$PY -m uvicorn apps.api.main:app --port 9000 >/tmp/light_api.log 2>&1 & P3=$!
trap 'kill $P1 $P2 $P3 2>/dev/null; pkill -P $P3 2>/dev/null; true' EXIT
sleep 8
total() { ps -axo pid=,ppid=,rss= | awk -v roots="$P1 $P2 $P3" 'BEGIN { n = split(roots, r, " "); for (i = 1; i <= n; i++) want[r[i]] = 1 } { pp[$1] = $2; rs[$1] = $3; ids[NR] = $1 } END { for (i = 1; i <= NR; i++) { q = ids[i]; while (q > 1) { if (q in want) { s += rs[ids[i]]; break } q = pp[q] } } printf "%.0f", s / 1024 }'; }
peak=0; sample() { t=$(total); [ "$t" -gt "$peak" ] && peak=$t; }
EMAIL="light$(date +%s)@e2e.dev"
TOKEN=$(curl -s -X POST localhost:9000/api/auth/register -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"password123\",\"persona\":\"ai_ml\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "idle total MB: $(total)"
curl -s -X POST localhost:9000/api/jobs/scout -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{"query":"RAG chatbot","limit":3}' >/dev/null
for i in $(seq 1 90); do
  sleep 4; sample
  S=$(curl -s localhost:9000/api/jobs -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;print(' '.join(sorted(set(x['status'] for x in json.load(sys.stdin)))))" 2>/dev/null)
  echo "t=$((i*4))s statuses=[$S] total MB: $(total)"
  case "$S" in *awaiting_approval*) break;; esac
done
sample; echo "PEAK total MB: $peak   (tools=$TOOLS)"
echo "processes counted: $(ps -axo pid=,ppid= | awk -v roots="$P1 $P2 $P3" 'BEGIN{n=split(roots,r," ");for(i=1;i<=n;i++)w[r[i]]=1}{pp[$1]=$2;ids[NR]=$1}END{for(i=1;i<=NR;i++){q=ids[i];while(q>1){if(q in w){c++;break}q=pp[q]}}print c}')"
