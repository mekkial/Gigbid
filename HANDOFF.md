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
- ✅ V1 decompose (project-level fusion; chunk-level result kept in rag_eval_v1_chunk_level_fusion.json), V4 outcome, V5 full, V8 corrective (threshold 0.45 calibrated on ai_ml, held out others: v8_threshold.json), `rag/variants/pipeline.py` (composable), ADR 0002 hypotheses, `rag_eval.json`, ablation runner (`rag_ablation.json` when finished)
- ✅ claim verifier `rag/verify.py` (LLM) + independent deterministic number-grounding check in proposal_eval
- 🔄 LLM evals running sequentially via `python -m evals.run_all decision tool proposals injection architecture` (log /tmp/run_all.log; results -> evals/results/*.json). Free tier = 8000 tokens/min + 1000 req/day PER MODEL: sizes are small on purpose (n=20 decision, 8/persona proposals, 16 arch)
- ⬜ judge calibration needs the USER's 30 human labels (`evals/runners/judge_calibration.py` to be written; CSV sheet)
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
### Phase 7 — prod
- ✅ tracing: Arize Phoenix (local server in `.local/phoenix-venv`, start: `PHOENIX_WORKING_DIR=$PWD/.local/phoenix .local/phoenix-venv/bin/python -m phoenix.server.main serve`, UI :6006); `agent/tracing.py`; verified 109 spans incl. gigbid.trace_id, node tokens/cost, LLM spans (`scripts/trace_demo.py`)
- ✅ CI files `.github/workflows/{ci,eval}.yml`, `evals/thresholds.yaml`, `evals/check_thresholds.py`, `scripts/check_{prompts,gigsim_frozen}.py`, Makefile, `infra/docker-compose.yml` + Dockerfiles (NOT run: no Docker locally)
- ✅ PII log filter, encrypted token vault, tenant-scoped queries, injection defence (delimiters + SECURITY clause + Compliance Guard); ASR measured by `injection_eval.py`
- ⬜ README table generator `scripts/make_readme_tables.py` (CI checks numbers trace to results), thresholds set from measured baseline, deployment (host undecided), Upwork live adapter, portfolio MCP packaging
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
- 2026-11-13 (late): throttle in agent/llm.py (token bucket per model), 'mid' tier = qwen3.8-27b for critic+liaison, reasoning_effort config. LLM eval suite launched (decision -> tool granularity -> proposals V0/V3 -> injection -> arch compare). Next while waiting: docs (DATA_CARD, ARCHITECTURE, RUNBOOK, EXTENSION, AI_USAGE), README generator, Upwork adapter, X3, packaging.

## STATE AT END OF SESSION 1 (2026-11-13, evening) — read this first
**Running now (background, started ~19:00):** `python -m evals.run_all ablation decision tool proposals injection architecture` (log `/tmp/run_all.log`).
 - done: decision_eval.json (n=20/persona, config A: bid/skip F1 0.92/0.87/0.92, scam recall 1.0; latency numbers include throttle queueing, NOT per-job latency)
 - the `rag ablation` child got SIGTERM after 113 s -> `evals/results/rag_ablation.json` is MISSING: rerun `python -m evals.runners.ablation` alone when nothing else is running (CPU/RAM heavy, ~25 min).
 - in progress/pending: tool_granularity (~2 h on free tier), proposal_eval V0 vs V3 (n=8/persona), injection_eval, arch_compare (n=16).
 - DO NOT edit agent/ or rag/ code while those subprocesses are still starting (each step re-imports the code).
 - Only ONE heavy process at a time (16 GB RAM; running ablation + evals + Phoenix together got processes killed).
**After the suite finishes, in this order:**
 1. rerun ablation (alone); optional config B/C decision comparison: `python -m evals.runners.decision_eval --n 12 --configs B C` (needs `evals/results/decision_eval.json` merge — it overwrites! copy A first)
 2. clean latency/budget run (sequential, concurrency 1, ~10 jobs) -> `evals/results/budget_run.json` (not written yet); one optimisation to report = parallel fit matcher (measure before/after) + token trimming
 3. change-request exercise (simulate: new GigSim rule + new policy rule); record lines changed / minutes taken in report section 6
 4. judge calibration: `python -m evals.runners.judge_calibration --make-sheet` then the USER labels 30 items, then `--score`
 5. X3 eval on real repos (needs GitHub token or local repos), `evals/results/x3_eval.json`
 6. set `evals/thresholds.yaml` from measured baseline; `python -m evals.runners.smoke_eval`; `python scripts/make_readme_tables.py`
 7. full `make test` + Playwright once more; build report PDF (HTML -> Playwright page.pdf; no pandoc), blog draft, resume bullets, viva cheat-sheet
**Needs the USER:** public GitHub repo + push; deploy host + reviewer password; Upwork account (for live mode + X6); 30 human judge labels (+ classmates pairwise panel); record the 3-min video; publish write-up; LangSmith/Phoenix public trace links; confirm real deadline; verify Kaggle dataset licences; Docker install to test compose.
**Demo assets:** docs/images/screens/*.png and demo.gif (slideshow); `node scripts/record_demo.mjs` re-records against the offline stack (`python scripts/e2e_stack.py` + `npx vite --port 3100`).

## Docker (installed Fri 22:30)
`brew install colima docker docker-compose` done; compose plugin path added to ~/.docker/config.json. VM NOT started (RAM): after the eval suite finishes run
`colima start --cpu 4 --memory 6 --disk 40` then `docker compose -f infra/docker-compose.yml up --build` and fix what breaks (compose never run yet). Stop with `colima stop` to free RAM.
Deadline: Sunday 2026-11-15 23:59 PKT (user confirmed "sunday night").

## UPDATE Sat 2026-11-14 ~01:30 (supersedes the "state at end of session 1" run notes)
**Root cause of the failed Groq evals:** free tier = 200,000 TOKENS PER DAY per model (not just 8k/min). gpt-oss-20b and qwen3.8-27b were exhausted by tool_granularity + earlier runs; proposals eval produced 0 results (all 429).
**Fixes done:** explicit max_tokens caps, prompt trimming (-35% evidence tokens), throttle, local Ollama profile (`MODEL_PROFILE=local`, qwen3:8b, `reasoning_effort=none`), results keyed/tagged by profile (`llm` field), decision rule budget-floor (+tests), injection-aware scam scan (+tests), change request done (docs/CHANGE_REQUEST.md, 5 lines/2 files), failure analysis (0 failures after fixes; pass1 kept), optimisation.json, ablation DONE (rag_ablation.json exists), VIVA.md, report builder.
**Running now:** `bash evals/run_local.sh` -> log /tmp/local_chain.log (decision A@local, proposals V0 vs V3 n=6, injection n=6, budget_run local, arch_compare n=10). Expect ~3-5 h from 01:20. Colima (Docker VM) is STOPPED to leave RAM for Ollama; restart after the chain: `colima start --cpu 4 --memory 5 --disk 40` then build (`docker compose -f infra/docker-compose.yml build`) — Dockerfile now uses CPU-only torch + generates synthetic data at build.
**After the chain:** (1) `python docs/report/build_report.py && node docs/report/make_pdf.mjs` (report currently 6 pages with pending sections); (2) `python scripts/make_readme_tables.py`; (3) judge sheet: `python -m evals.runners.judge_calibration --make-sheet` -> USER labels; (4) decision B/C + tool-granularity `mid:tuned` re-run on Groq only when quota resets (rolling 24h; ~22k tokens needed for the tuned cell); (5) docker compose build/up test; (6) thresholds.yaml from smoke/decision numbers; (7) full tests (70 pass at 01:10) + Playwright; (8) blog draft + resume bullets; (9) fill VIVA.md items 8-10.
**Blocking for the USER (morning):** Groq paid quota or another provider for the DEPLOYED app; deploy host; GitHub repo; judge labels; video; Upwork account (optional).

## UPDATE Sat 05:05 — evals DONE, docker VERIFIED
* All local-profile evals finished (decision A@local, proposals V0/V3 n=18/arm, injection (strict metric), budget_run_local, arch_compare n=10, failure analysis, optimisation); report PDF `docs/report/report.pdf` (7 pages) built by `python docs/report/build_report.py && node docs/report/make_pdf.mjs`; README tables regenerated; blog draft `docs/BLOG_DRAFT.md` (~1500 words); `docs/RESUME_BULLETS.md`; `docs/VIVA.md` (items 8-10 need filling); `docs/LABELLING_GUIDE.md` + judge sheet.
* Docker/Colima: compose stack ran; kill-resume drill PASSED (evidence file). Colima is RUNNING with 6 GB (stop with `colima stop` to free RAM). Ollama server was stopped (restart: `OLLAMA_FLASH_ATTENTION=1 ollama serve`).
* Tests: 81 offline (79 + pii) + 7 Playwright (last Playwright run was BEFORE decision/risk/compliance changes — rerun once).
* STILL OPEN: judge labels (user), decision configs B/C + tool-granularity `mid:tuned` re-run on Groq (quota is partially back: analyst/writer calls worked at 04:55), deploy host + paid quota decision (user), GitHub repo/push (user), video (user), VIVA items 8-10, final README/report refresh, Playwright rerun, smoke_eval + thresholds, push.

## STATE Sat 2026-11-14 ~06:20 (autonomous overnight session finished) — START HERE
**Done & committed (git log is current):** everything in the plan except the user-dependent items below.
 * Tests: 84 offline (`make test`), 7 Playwright (rerun 05:29, all pass), CI-gate scripts verified locally (`evals/run_smoke_local.sh`: F1 1.0, scam recall 1.0, unsupported 0.0 -> gate passes).
 * Docker/Colima: compose stack ran, kill-and-resume drill passed (`docs/evidence/`). Colima, Ollama, Phoenix are all STOPPED now (RAM).
 * Report PDF `docs/report/report.pdf` (7 pages; rebuild: `python docs/report/build_report.py && node docs/report/make_pdf.mjs`), README tables (`python scripts/make_readme_tables.py`), blog draft, resume bullets, viva sheet (item 8 awaits labels), change request, trace exports `docs/traces/`, deploy script + checklist `docs/DEPLOY.md`.
 * Findings worth remembering for the viva: decomposition hurt (ablation), budget-floor rule fixed the biggest failure group, injection-aware scam scan opened a documented hole, free-tier TPD cap, Critic loop never approves (length fixed 0/9->7/9 rounds, personalisation 0.4 remains), loose injection metric artifact, single-agent baseline lost on FORMAT not judgement, supervisor tokens undercounted.
**Known gaps (be honest about them):** tool-granularity `mid:tuned` cell invalid (needs Groq quota; script supports `python -m evals.runners.tool_granularity mid:tuned`); hosted-profile budget not measured (qwen quota; `MODEL_PROFILE=open python -m evals.runners.budget_run`); decision configs B/C comparison not run on hosted models (`python -m evals.runners.decision_eval --n 12 --configs B C`); judge uncalibrated; pairwise human panel not done; X3 not run on real repos; Upwork live untested against real server; CI workflows never run on GitHub; phoenix/ollama/caddy compose services not exercised; hidden test run n/a.
**Needs the USER (in this order of urgency):** (1) deploy host + Groq Dev-tier key (free tier cannot serve grading) -> `docs/DEPLOY.md`; (2) GitHub repo: create public repo and push (commits so far: early ones carry the user's personal email as author; later ones use gigbid-dev@users.noreply.local — offer to rewrite history before publishing); (3) 30 judge labels `docs/LABELLING_GUIDE.md` then `python -m evals.runners.judge_calibration --score`; (4) 3-minute demo video (script: inbox -> approve -> scam caught -> injection ignored -> client reply); (5) publish the write-up; (6) confirm deadline (Sunday night per user); (7) Upwork account optional; (8) verify Kaggle licences.
**After the user acts:** rebuild report + README tables, fill README TODO links (live URL, video, write-up, traces), run `python scripts/check_gigsim_frozen.py`, `python scripts/check_prompts.py`, `python scripts/make_readme_tables.py --check`, final `make test`, push.
