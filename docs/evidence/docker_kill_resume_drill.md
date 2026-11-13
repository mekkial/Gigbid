# Evidence: crash-and-resume drill, run in Docker (Colima, arm64), 2026-11-14 ~05:00 PKT

Stack: `docker compose -f infra/docker-compose.yml up -d postgres redis gigsim mcp-marketplace api worker web` (GIGBID_TOOLS=mcp, Arq worker on Redis,
Postgres checkpointer, hosted open profile on Groq). User `u_f03e241fbe`, job `ai_ml-job-0007`, a good-fit RAG job.

| step | observed |
|---|---|
| proposal reached the human gate | `GET /api/approvals` lists thread `u_f03e241fbe:ai_ml-job-0007`; draft 918 chars, dry-run Connects cost 16, ends with the mandatory AI-disclosure sentence |
| `docker compose kill -s SIGKILL api worker` while it waits | both containers killed |
| `docker compose up -d api worker` | healthy again in ~10 s |
| pending approval after restart | **still listed** (rebuilt from the Postgres checkpoint) |
| approve twice, concurrently | second request **HTTP 409** (atomic `awaiting_approval -> resuming` claim) |
| run status | `submitted` |
| marketplace state (queried INSIDE the compose network, `http://gigsim:8081`) | **1 proposal** `prop-37a99663e2`, status `submitted`; balance **200 -> 184** (exactly one 16-Connect debit) |
| MCP audit ledger (marketplace server) | rows for `create_proposal_draft` and `submit_proposal` carry the acting user id and the trace id |

Note on a false alarm during the drill: querying `localhost:8081` from the host returned a different GigSim (a stale host process from earlier development still held the port), which made it look
as if nothing was submitted. Querying inside the compose network gave the real state above. The stale process was stopped.

Not covered by this drill: the Phoenix and Ollama services (not started), the Caddy HTTPS profile, and a literal power-loss during the submit call itself (idempotency keys cover that case; see `tests/integration/test_bid_graph.py`).
