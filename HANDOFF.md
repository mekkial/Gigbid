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
- ✅ Portfolio / Marketplace (HTTP+bearer, idempotency, dry_run, audit, rate limit) / Workspace MCP servers + tests
- ✅ `agent/mcp_client.py` (MultiServerMCPClient, allowlists, retries, degraded mode+recovery), schema snapshot tests, `docs/TOOLS.md`
- ✅ e2e through real MCP + live Groq: `scripts/e2e_mcp.py` (needs GigSim :8081 and marketplace MCP :8082 running; see Log)
- ⬜ Upwork live adapter (`upwork_live.py`, needs Upwork account), R&D-A tool-granularity eval (`evals/runners/tool_granularity.py`)
### Phase 3 — RAG
- ✅ Ingestion with metadata, dense+BM25 index, V0/V2/V3, `evals/runners/rag_eval.py` → `evals/results/rag_eval.json`
- ⬜ V1 decomposition, V4 outcome-aware, V8 corrective, claim verifier, judge calibration, ablation, GigSim outcome eval
### Phase 4 — graphs
- ✅ `agent/handoffs.py` (Pydantic), `agent/state.py` (reducers), `agent/prompts/*.v1.md`, nodes (scout/analyst/risk/fit/pricing/writer/verify/critic/compliance/liaison), `agent/tools.py` (allowlists)
- ✅ `agent/graphs/bid_graph.py`: parallel Send fan-out, decide, pricing, writer->verify->critic loop (<=2), compliance, interrupt approval, idempotent submit
- ✅ memory: `agent/memory/{store,promotion_rules}.py` (style + outcome, PostgresStore), async checkpointer `agent/checkpoint.py` (Postgres/SQLite)
- ✅ tests/integration/test_bid_graph.py (scam skip, injection, bounded critic, exactly-once, reject, edit->style memory, crash-resume) — 16 tests pass
- ✅ conversation graph (`agent/graphs/conversation_graph.py`) + tests; graphs rendered to `docs/images/*.mmd` (`scripts/render_graphs.py`)
- ✅ live-LLM e2e: 24.8s, ~15k tokens, ~$0.0046 list cost, 1 critic revision, submitted, client replied
- ⬜ R&D-C comparison (single ReAct vs supervisor vs graph), fit_matcher is slow (9.5s: sequential per-requirement MCP searches) -> parallelise
### Phase 5 — API + worker
- ✅ `apps/api/` (FastAPI): auth (scrypt+JWT), settings, jobs/inbox, runs+SSE stream+history/replay, approvals (atomic check-and-set -> exactly-once), proposals/studio/regenerate/pipeline, messages, analytics, memory viewer, portfolio upload (incremental index), /health/tools (degraded banner source), trace-id middleware, PII log filter, encrypted token vault
- ✅ `worker/` Arq tasks (run_bid, scout, resume_run, run_conversation, replay_run, cron scout_saved_searches + retry_waiting); queue falls back inline w/o Redis
- ✅ tests/api (9 pass; uses DB `gigbid_test`, offline LLM stubs). Redis on :6380 (`redis-server --port 6380 --daemonize yes --dir .local`)
- ⬜ run Arq worker for real once (`arq worker.settings.WorkerSettings`) + worker-restart test
### Phase 6 — Web UI + Playwright
- ✅ `apps/web` (Vite+React+TS): login, onboarding, inbox, job detail (req->evidence matrix), proposal studio (EvidenceHover, regenerate paragraph, approve/edit/reject, dry-run), pipeline kanban, messages, run viewer (SSE), analytics, settings (memory viewer), degraded banner, responsive. TS client generated: `scripts/export_openapi.py` then `npx openapi-typescript openapi.json -o src/lib/api/schema.d.ts`
- ✅ Playwright: 7 pass (`cd apps/web && npx playwright test`; starts `scripts/e2e_stack.py` offline stack on :8100/:8101 + vite :3100). Report in apps/web/playwright-report
- ⬜ production build check (`npm run build`), screenshots/GIF for README
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
- 2026-11-13: MCP servers + client + conversation graph done; 39 tests pass.
  Servers for manual runs: `set -a; . ./.env; set +a; export GIGSIM_API_TOKEN=dev-token GIGSIM_BASE_URL=http://127.0.0.1:8081`
  `.venv/bin/uvicorn gigsim.app:app --port 8081 &` ; `.venv/bin/python -m mcp_servers.marketplace.server &` (port 8082)
- 2026-11-13: API + worker done; 48 tests pass total. Next: web UI (apps/web), then evals.
- 2026-11-13: Web UI + 7 Playwright tests pass. Next: evals (V1/V4/V8, decision, injection ASR, claim verification, tool granularity, arch comparison), then CI/compose/docs/report, X3, Upwork adapter.
