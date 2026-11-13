# Résumé bullets (every number traces to a file in `evals/results/`)

**Two-line version**
- Built GigBid, a LangGraph multi-agent freelance copilot (3 own MCP servers, durable human-approval gates, FastAPI + React/TS, Arq worker); hybrid retrieval + reranking lifted evidence MRR from 0.63 to 0.92, and claim verification cut proposals containing an unsupported claim from 50% to 0% (n=18 per arm).
- Found by failure taxonomy that a 12-line budget-floor rule fixed 24 of 30 dev failures (bid/skip F1 0.89 → 0.98 on 240 jobs), while the "advanced" query-decomposition variant *hurt* MRR (0.47 vs 0.92); ran all evals on a local Qwen3-8B at 11.5k tokens and 164 s p95 per proposal, with 80+ automated tests.

| claim | file |
|---|---|
| MRR 0.63 → 0.92 (V0 → V3), decomposition 0.45, composed 0.47 vs 0.92 without decomposition | `rag_eval.json`, `rag_ablation.json` |
| unsupported claims 50% (V0, before verification) → 0% (V3, after) | `proposal_eval.json` |
| 30 failures → 6 → 0; F1 0.894 → 0.977 (pass 1) | `failure_analysis_pass1.json`, `failure_analysis.json` |
| 11.5k tokens, 164 s p95 per proposal, $0 | `budget_run_local.json` |

**Honest scope to keep in mind when you talk about it:** synthetic corpus and simulator I wrote; small samples (n=18 per arm, 10 jobs in the architecture comparison); evaluation numbers come from a local 8B model, not the hosted models.

**One-line portfolio summary:** "Multi-agent bidding copilot with evidence-grounded proposals and human-in-the-loop approvals; measured, ablated and honest about what did not work."
