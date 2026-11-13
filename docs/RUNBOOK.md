# Runbook

## Verification status (honest)
| Item | Status |
|---|---|
| Unit, contract, integration, API tests | run and passing locally (`make test`) |
| Playwright (7 tests) | run and passing locally against the offline stack |
| `docker compose up` | **executed locally (Colima, arm64)**: both images built (python image 5.1 GB, web 76 MB), 7 services up and healthy, scouting through the Arq worker and MCP servers worked, and the SIGKILL-and-resume exactly-once drill passed: `docs/evidence/docker_kill_resume_drill.md`. Not exercised: the `phoenix` and `ollama` services, the Caddy HTTPS profile, an x86 host. Bugs the real run found and fixed: PII log filter broke uvicorn access logs; Dockerfile pulled CUDA wheels. |
| Public deployment | **not done** (host undecided). See "Deploy". |
| Upwork live mode | adapter + OAuth implemented and tested with fakes; **not run against the real Upwork server** (no account yet) |
| GitHub Actions | workflows written; never run on GitHub |

## LLM providers and quotas (important for deployment)
* **Hosted open profile (Groq, free tier):** 8,000 tokens/min **and 200,000 tokens/day per model**. A proposal costs ~15-20k tokens, so the free tier serves roughly a dozen proposals per model per day. That is enough for development, **not** for a reviewer plus a hidden grading run. Before deploying, add paid quota (Groq Dev tier is pay-as-you-go; list-price cost per proposal is about $0.005) or point `agent/config.yaml` at another OpenAI-compatible provider.
* **Local profile (`MODEL_PROFILE=local`):** Ollama `qwen3:8b` on a 16 GB laptop, ~13-18 tokens/s, thinking disabled (`reasoning_effort: none`, 7x faster), no quota. Used for the larger evaluations; results files are keyed by profile.
* The client throttles per model (`agent/llm.py::_Throttle`) and fails over to the fallback model, but **cannot beat a daily cap**.

## Run locally (no Docker)
```bash
cp .env.example .env            # add GROQ_API_KEY (free: console.groq.com/keys); never commit .env
make install                    # uv venv + deps + npm ci
# Postgres 16+ and Redis must be running; DATABASE_URL / REDIS_URL in .env
make seed                       # synthetic data (+ Kaggle jobs if data/raw/ has the CSVs); needs REVIEWER_PASSWORD
make dev                        # GigSim :8081, marketplace MCP :8082, API :8000, worker, web :3000
```
Offline tests need no key: `make test`. Playwright: `cd apps/web && npx playwright test`.

## Configuration surfaces (change behaviour without code)
* `agent/config.yaml`: model per node (tier -> model), thresholds, budgets, retrieval variant, live-mode switches.
* `data/policy_pack/policy_rules.yaml`: forbidden patterns, banned phrases, scam signals, injection patterns, length limits.
* `gigsim/rules.yaml`: simulator rules (rate limit, Connects costs, reply model). The policy-change exercise edits only these files.

## Live mode (Upwork) and polling
`marketplace.mode: upwork_live` is the only switch; graphs and nodes are unchanged because they only see `MarketplacePort`.
Saved searches in live mode may not run more often than `marketplace.live.min_poll_interval_min` (180 min): job feeds change slowly,
a few reads per day is enough to be useful, and anything faster starts to look like scraping. Reads are also spaced >= 2 s per request.
Writes are drafts only; the user confirms on Upwork.

## Failure drills
* **Kill the marketplace MCP server:** the UI banner appears within ~5 s (`/api/health/tools`), runs that hit it are parked as `waiting_marketplace`, `retry_waiting` (cron, 30 s) resumes them after recovery. Code: `agent/mcp_client.py` (retries/circuit), `apps/api/runtime.py::execute`, `worker/tasks.py::retry_waiting`.
* **Crash the API/worker while a proposal waits for approval:** restart; the pending approval is rebuilt from the checkpoint; approve in the UI; the submit uses the thread-derived idempotency key, so it is sent once.
* **LLM provider limits:** `agent/llm.py` throttles per model (7,000 tokens/min of the 8,000 allowed), falls back to the fallback model, then fails the node; LangGraph retries (3x, exponential), then the run becomes `dead_letter`.

## Deploy
Any host that can run the compose file works (a single small VM is simplest). Needs: HTTPS in front of the `web` service, `.env` with real secrets
(`APP_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `GROQ_API_KEY`, `MARKETPLACE_TOKENS`), `REVIEWER_PASSWORD` for the seeded reviewer, and the deployment must use the
**open** profile (hosted open models via Groq). Reviewer credentials go in the Classroom private comment, never in the repo.
