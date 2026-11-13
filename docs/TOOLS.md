# MCP Tool Catalogue

Every capability an agent can use is an MCP tool with a schema, an owner and a test. Agents never call GigSim, Upwork,
a database or a file directly. Per-agent allowlists live in `agent/tools.py` (`NODE_TOOL_ALLOWLIST`) and are enforced by
`agent/mcp_client.py`. Signatures are frozen by `tests/contract/snapshots/*.json` (CI fails on unintended change).

| Tool | Server | R/W | Annotations (RO / destructive / idempotent) | Auth | Used by |
|---|---|---|---|---|---|
| search_evidence | portfolio | read | ✔ / ✘ / ✔ | none (stdio, local) | fit_matcher, writer, critic, liaison |
| get_case_study | portfolio | read | ✔ / ✘ / ✔ | none (stdio) | writer |
| list_skills | portfolio | read | ✔ / ✘ / ✔ | none (stdio) | fit_matcher |
| search_jobs | marketplace | read | ✔ / ✘ / ✔ | Bearer | scout |
| get_job | marketplace | read | ✔ / ✘ / ✔ | Bearer | scout, risk_assessor |
| get_client_history | marketplace | read | ✔ / ✘ / ✔ | Bearer | risk_assessor |
| get_connects_balance | marketplace | read | ✔ / ✘ / ✔ | Bearer | pricing |
| get_market_stats | marketplace | read | ✔ / ✘ / ✔ | Bearer | pricing |
| list_messages | marketplace | read | ✔ / ✘ / ✔ | Bearer | client_liaison |
| create_proposal_draft | marketplace | write (draft) | ✘ / ✘ / ✔ | Bearer + idempotency key + dry_run | submit step (after approval) |
| submit_proposal | marketplace | write (spends Connects) | ✘ / ✔ / ✔ | Bearer + idempotency key + dry_run | submit step (after approval) |
| send_message | marketplace | write | ✘ / ✔ / ✔ | Bearer + idempotency key + dry_run | client_liaison (after approval) |
| free_slots | workspace | read | ✔ / ✘ / ✔ | none (stdio) | client_liaison |
| create_tentative_hold | workspace | write (tentative only) | ✘ / ✘ / ✔ | none (stdio) | client_liaison |
| create_email_draft | workspace | write (draft only, never sent) | ✘ / ✘ / ✘ | none (stdio) | client_liaison |

Resource templates (portfolio): `portfolio://case/{id}`, `portfolio://proposal/{id}`.
Prompts (portfolio): `answer_screening_question`, `summarise_fit`, `draft_cover_letter`.

## Marketplace server guarantees
* Pydantic-constrained inputs (e.g. cover letter 150-3000 chars, bid > 0, idempotency key >= 8 chars) and declared output schemas.
* **Idempotency:** server-side ledger keyed by (user, tool, key); a retried write returns the stored result (`replayed: true`) and never repeats the effect. GigSim itself is idempotent too (defence in depth).
* **dry_run:** returns exactly what would be sent and its Connects cost; shown on the approval screen.
* **Auth/limits:** bearer token on the HTTP endpoint (`MARKETPLACE_TOKENS`), per-user token bucket (40/min) under GigSim's 60/min.
* **Audit:** append-only SQLite table (UPDATE/DELETE blocked by triggers) with user, tool, PII-masked arguments, result, trace id.

## Third-party servers (trust rationale)
| Server | Why we trust it | Scope we grant |
|---|---|---|
| Upwork official MCP (`https://mcp.upwork.com/mcp`, OAuth 2.1) | First-party platform endpoint; the only permitted way to touch live Upwork (no scraping). | Read on a conservative schedule; writes only as drafts after in-app approval; user confirms on Upwork. Tokens encrypted per user. |
| GitHub MCP server (repo ingestion, X3) | Official GitHub-maintained server; read-only token limited to the user's public repos. | `repo:read` only. |

## Live adapter status
`mcp_servers/marketplace/adapters/upwork_live.py` is implemented behind the same `MarketplacePort`; it needs a real Upwork account
to be exercised (not graded on outcomes). See `docs/RUNBOOK.md`.
