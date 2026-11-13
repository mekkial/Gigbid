.PHONY: dev install test eval eval-smoke seed demo lint web-build gen-api ci-checks
PY ?= .venv/bin/python

install:
	uv venv --python 3.12 .venv && uv pip install -e ".[dev]" && cd apps/web && npm ci

dev:            ## run everything locally: GigSim, marketplace MCP, API, worker, web (needs Postgres + Redis running, see docs/RUNBOOK.md)
	bash scripts/dev.sh

seed:           ## regenerate data (synthetic personas + dev sets), process real Kaggle jobs if present, create reviewer account
	$(PY) -m data.build.gen_data
	-$(PY) -m data.build.prepare_jobs
	$(PY) scripts/seed_reviewer.py

demo: seed dev

test:           ## unit + contract + integration + API tests (offline, no API cost)
	$(PY) -m pytest tests mcp_servers -q
	$(PY) scripts/check_prompts.py

lint:
	.venv/bin/ruff check agent apps rag evals mcp_servers worker scripts tests --select E9,F63,F7,F82,F401 --ignore F401
	$(PY) scripts/check_prompts.py

eval:           ## FULL evaluation -> evals/results/*.json (uses the LLM; slow on free-tier limits)
	$(PY) -m evals.run_all

eval-smoke:     ## 30-job smoke eval used by CI, then the threshold gate
	$(PY) -m evals.runners.smoke_eval
	$(PY) evals/check_thresholds.py

gen-api:        ## regenerate the TypeScript client from FastAPI's OpenAPI schema
	$(PY) scripts/export_openapi.py && cd apps/web && npx openapi-typescript openapi.json -o src/lib/api/schema.d.ts

web-build:
	cd apps/web && npm run build

ci-checks:
	$(PY) scripts/check_prompts.py && $(PY) scripts/check_gigsim_frozen.py && $(PY) scripts/make_readme_tables.py --check
