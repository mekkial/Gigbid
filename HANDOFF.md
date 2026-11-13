# GigBid — Handoff / Progress Log

Plan: `/Users/mekkialbilal/.claude/plans/draft-a-complete-plan-sparkling-tulip.md`
Project root: `/Users/mekkialbilal/Downloads/Agentic assignment 2/gigbid` (venv: `.venv`, run with `.venv/bin/python`)
Rules: no Co-Authored-By trailers in commits. Secrets only in `.env` (git-ignored). LLM = Groq (open profile), models in `agent/config.yaml`.
Local Postgres 17 runs on port 5433 (`.local/pgdata`, start: `/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D .local/pgdata -o '-p 5433 -k /tmp' start`); DATABASE_URL in .env.
Missing locally: Docker, Ollama (write compose files, can't run them). macOS has no `timeout` cmd. OpenRouter key not used (billing).

## How to resume
1. `cd` to project root; `git log --oneline` to see last step.
2. Run `.venv/bin/python -m pytest -q` (all should pass), then continue at the first unchecked step below.

## Steps (✅ done · 🔄 in progress · ⬜ todo)
### Phase 0 — bootstrap
- ✅ Repo from starter kit, pyproject, config.yaml, `agent/llm.py` (node→tier→model from config), `.env.example`
### Phase 1 — data + GigSim
- ✅ `data/build/gen_data.py`: 3 synthetic personas, 80 clients, 630 jobs, dev sets in `evals/datasets/` (gold labels)
- ✅ `data/build/prepare_jobs.py`: REAL Kaggle jobs (3000) + `market_stats.json` (Kaggle 60k + 50k)
- ✅ `gigsim/` simulator (auth, rate limit, 5xx, Connects, idempotency, hidden client prefs); tests pass
- ✅ `data/policy_pack/policy_rules.yaml` (machine-readable rules)
- ⬜ `docs/DATA_CARD.md`
### Phase 2 — MCP / port
- ✅ `agent/marketplace_port.py` + GigSim adapter (retries, dry_run)
- ⬜ Portfolio MCP server, Marketplace MCP server (auth, idempotency, audit), Workspace MCP server
- ⬜ `agent/mcp_client.py` (allowlists, timeouts, degraded mode), Upwork live adapter (needs Upwork account), schema snapshot tests, `docs/TOOLS.md`, R&D-A tool-granularity eval
### Phase 3 — RAG
- ✅ Ingestion with metadata, dense+BM25 index, V0/V2/V3, `evals/runners/rag_eval.py` → `evals/results/rag_eval.json`
- ⬜ V1 decomposition, V4 outcome-aware, V8 corrective, claim verifier, judge calibration, ablation, GigSim outcome eval
### Phase 4 — graphs
- ✅ `agent/handoffs.py` (Pydantic), `agent/state.py` (reducers), `agent/prompts/*.v1.md`, nodes (scout/analyst/risk/fit/pricing/writer/verify/critic/compliance/liaison), `agent/tools.py` (allowlists)
- ✅ `agent/graphs/bid_graph.py`: parallel Send fan-out, decide, pricing, writer->verify->critic loop (<=2), compliance, interrupt approval, idempotent submit
- ✅ memory: `agent/memory/{store,promotion_rules}.py` (style + outcome, PostgresStore), async checkpointer `agent/checkpoint.py` (Postgres/SQLite)
- ✅ tests/integration/test_bid_graph.py (scam skip, injection, bounded critic, exactly-once, reject, edit->style memory, crash-resume) — 16 tests pass
- ⬜ conversation graph, live-LLM end-to-end run, R&D-C comparison, graph PNG render
### Phase 5 — API + worker  ⬜
### Phase 6 — Web UI + Playwright  ⬜
### Phase 7 — prod (CI, tracing, guardrails, compose, deploy)  ⬜
### Phase 8 — X3 Portfolio builder  ⬜
### Phase 9 — change request, docs, README, report, video, write-up  ⬜

## Key results so far (files in `evals/results/`)
- rag_eval.json (40 jobs/persona, synthetic dev set): V0 R@5 0.90–0.95 / MRR 0.57–0.69; V2 R@5 0.98–1.0; V3 MRR 0.87–0.93, ~0.6 s/query.

## Needs from the user
- Real deadline (PDF says 12 Nov 2026, already past). Upwork account when reaching live adapter. Deploy host choice. Docker install for compose.

## Log
- 2026-11-13: Phases 0–1 done, RAG V0/V2/V3 measured.
- 2026-11-13: Nodes + bid graph + memory done; 16 tests pass.
