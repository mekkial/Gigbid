# GigBid — a multi-agent freelancer copilot where a human approves every send

GigBid finds freelance jobs, decides whether each is worth bidding on, writes proposals in which **every claim links to portfolio evidence**, and
manages the client conversation. A team of LangGraph agents does the legwork; **you approve every proposal and message** before anything leaves the system.

> **Live demo:** _TODO: public URL + reviewer login (private comment on the submission)_ · **3-minute video:** _TODO_ · **Traces:** _TODO: 3 public trace links (see `docs/RUNBOOK.md`)_
> **Portfolio MCP server:** `uvx --from ./mcp_servers/portfolio gigbid-portfolio-mcp` (see `mcp_servers/portfolio/README.md`) · **Write-up:** _TODO_

![GigBid demo: onboarding, inbox, job detail, evidence on hover, approval, pipeline, analytics](docs/images/demo.gif)

## What is real and what is not (read this first)
| | Status |
|---|---|
| Agents, graphs, MCP servers, API, web UI, worker | implemented; unit/contract/integration/API tests and 7 Playwright tests pass locally |
| Marketplace | **GigSim**, a simulator I wrote (the instructor's GigSim was not available to me). Live Upwork adapter is implemented and tested against a fake Upwork-style MCP server only |
| Data | real Kaggle Upwork jobs for the stream and prices; **synthetic** personas, proposals, clients, scams, injections and labels (`docs/DATA_CARD.md`) |
| Docker / public deploy / GitHub Actions | files written, **not yet run** (`docs/RUNBOOK.md`) |
| LLM judge | uncalibrated until the 30 human labels are added (`evals/runners/judge_calibration.py`) |
| LLM quota | Groq's free tier caps **200,000 tokens/day per model**; evaluation beyond the first experiments therefore ran on a **local Qwen3 8B (Ollama)**. Every results file records which models produced it (`llm` field). The hosted deployment needs paid quota (see `docs/RUNBOOK.md`) |
| Evaluation sizes | small, because the free LLM tier allows 8,000 tokens/min per model; each results file records its `n` and confidence intervals |

## Architecture
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Bid graph (Job Analyst ∥ Risk Assessor ∥ Fit Matcher → decide → price → write → verify claims → Critic (≤2 loops) → Compliance → **human approval** → submit) and conversation graph:

![bid graph](docs/images/bid_graph.png)

Key properties: one marketplace port with two adapters (simulator / live Upwork); three own MCP servers plus the official Upwork and GitHub servers;
`interrupt()` approvals that survive restarts and submit exactly once; style and outcome memory written only through explicit promotion rules;
prompts, policy, thresholds and models live in config, not code.

## Quick start
```bash
cp .env.example .env         # add GROQ_API_KEY (free), never commit .env
make install && make test    # offline, no API cost
make seed && make dev        # needs Postgres + Redis; see docs/RUNBOOK.md
```

## Results
Every number below is generated from `evals/results/*.json` by `scripts/make_readme_tables.py` (CI fails if the README is stale).
Corpus is synthetic and templated: read absolute numbers as optimistic and the *ordering* as the finding. Hypotheses were written before running: `docs/adr/0002-rag-hypotheses.md`.

### Retrieval variants (R&D question B)
<!-- BEGIN:rag -->
_n = 60 jobs per persona, macro-average over 3 personas; source `evals/results/rag_eval.json`_

| variant | Recall@5 | MRR | nDCG@10 | p95 s/query | abstain on skip jobs (per persona) |
|---|---|---|---|---|---|
| v0_naive | 0.906 | 0.6289 | 0.7008 | 0.0082 | 0.0/0.0/0.0 |
| v1_decompose | 0.9231 | 0.4542 | 0.5757 | 0.0354 | 0.0/0.0/0.0 |
| v2_hybrid | 1.0 | 0.7372 | 0.8052 | 0.0085 | 0.0/0.0/0.0 |
| v3_rerank | 1.0 | 0.9174 | 0.939 | 0.7348 | 0.0/0.0/0.0 |
| v4_outcome | 1.0 | 0.7372 | 0.8052 | 0.0094 | 0.0/0.0/0.0 |
| v5_full | 0.8804 | 0.4693 | 0.5864 | 2.7322 | 0.0/0.0/0.0 |
| v8_corrective | 0.9487 | 0.8747 | 0.894 | 1.3526 | 1.0/1.0/1.0 |
<!-- END:rag -->

### Ablation of the full pipeline (one component removed at a time)
<!-- BEGIN:ablation -->
_not run yet_
<!-- END:ablation -->

### End-to-end proposals: V0 vs the shipped variant (simulated human approves unchanged)
<!-- BEGIN:proposals -->
_not run yet_
<!-- END:proposals -->

### Is multi-agent worth it? (R&D question C)
<!-- BEGIN:arch -->
_not run yet_
<!-- END:arch -->

### Tool granularity (R&D question A)
<!-- BEGIN:tools -->
_not run yet_
<!-- END:tools -->

### Prompt-injection attack success rate
<!-- BEGIN:injection -->
_not run yet_
<!-- END:injection -->

## Signature extension: X3 Portfolio builder
A GitHub repo becomes a case study in which every claim is verified against the code before it is published: skills must appear in the code or manifests,
"results" must be measurable and the number must exist in the repo, cited files must exist, and the rest is graded by the claim verifier.
See [docs/EXTENSION.md](docs/EXTENSION.md) and `tests/unit/test_portfolio_builder.py`.

## Safety and platform respect
Never sends without approval; never scrapes (official Upwork MCP only; live mode creates drafts you confirm on Upwork); polite polling floor of 180 minutes in live mode;
job posts and client messages are untrusted data (delimiters, a SECURITY clause, a deterministic scan and a Compliance Guard); emails/phones/cards are masked in logs and audit;
OAuth tokens are encrypted per user. What still gets through is in the injection results and `docs/RUNBOOK.md`.

## Layout
`agent/` graphs, nodes, prompts, memory · `rag/` ingestion, variants, verification · `mcp_servers/` portfolio, marketplace, workspace · `gigsim/` simulator ·
`apps/api` FastAPI · `apps/web` React/TypeScript · `worker/` Arq · `evals/` runners and results · `tests/` · `infra/` Docker · `docs/` ADRs, data card, tools, runbook.

Pinned versions: see `pyproject.toml` (Python 3.12, LangGraph 1.2, MCP SDK 1.30, FastAPI) and `apps/web/package.json` (React 18.3, Vite 5.4).
