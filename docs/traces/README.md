# Trace artifacts

The brief asks for public trace links. A public link needs a hosted tracing account (LangSmith, Langfuse Cloud, Phoenix Cloud) that only the author can create, so what is in the repo are
**real exported traces** from the local Arize Phoenix server (OpenTelemetry spans; the same instrumentation would feed a hosted backend by changing `PHOENIX_COLLECTOR_ENDPOINT`):

| file | scenario | what to look at |
|---|---|---|
| `trace-skipped_scam-12b991.json` | an unpaid-trial / off-platform scam | 14 spans: analyst, risk assessor (deterministic scan flags `unpaid_work`, `off_platform_contact`), fit matcher, **decide -> skip**; 722 tokens, ~$0.00009: no writer ever runs |
| `trace-approved_proposal-020359.json` | a good-fit job through to approval | 59 spans: **three writer -> verifier -> critic rounds (the Critic asked for two revisions)**, compliance, then the pause at approval; 21,011 tokens, ~$0.0049 at list price; per-node `gigbid.tokens` / `gigbid.cost_usd` attributes and 15 LLM spans with token counts |
| `../evidence/docker_run_checkpoint_history.json` | **crash-and-resume**: API and worker SIGKILLed while the proposal awaited approval | 18 checkpoints; the pause at `approval` (step 14), then `approved` and `submitted`; the marketplace saw exactly one submission (`../evidence/docker_kill_resume_drill.md`) |

Every `run` span carries `gigbid.trace_id`, the id that also appears in the MCP audit log and (via `x-trace-id`) on the API response.
To publish: run the same jobs with a hosted backend configured, make the three traces public, and put the links in the README.
