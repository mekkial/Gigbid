# ADR 0001 — Major choices

* **Hand-written LangGraph graphs**, not a prebuilt agent: parallel branches, bounded loops and `interrupt()` need to be explicit. Compared against a ReAct agent and `langgraph-supervisor` in `evals/results/arch_compare.json`.
* **One marketplace port, two adapters** (GigSim, Upwork): the live/sim switch is config only (viva question 7).
* **Deterministic steps wherever possible** (fit matrix, pricing, compliance, risk rules): cheaper, testable, and they cannot be talked out of a decision by a prompt injection.
* **Postgres for everything durable** (checkpoints, store, users, runs); SQLite fallback only for tests/dev without a DB.
* **Phoenix for tracing** (OpenTelemetry): pip-installable, self-hostable, testable without Docker.
* **Per-model throttle in the client**: the free tier allows 8,000 tokens/min per model; blocking in the client is better than 429 storms.
* **Writer/Critic on different model families** (gpt-oss-120b vs Qwen 27B): avoids self-review and spreads the free-tier budgets.
* **Open models first**: Groq-hosted open-weight models for the shipped profile; the `paid` profile exists in config but was not run.
