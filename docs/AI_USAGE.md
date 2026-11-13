# AI usage disclosure

| Tool | Used for | Files |
|---|---|---|
| Claude Code (Claude Opus 5.5 / Sonnet 5.5) | Wrote most of the first drafts of the code in this repository under my direction, plus tests and documentation; ran the experiments and reported their outputs | essentially all of `agent/`, `rag/`, `mcp_servers/`, `apps/`, `worker/`, `evals/`, `tests/`, `scripts/`, `docs/` |
| Groq-hosted open models (gpt-oss-20b/120b, Qwen3.8-27B) | The product's own LLM nodes and the LLM judge (runtime, not coding) | `agent/config.yaml` |

I am accountable for every line. Things the assistant got wrong that were caught while running the system (not by re-reading):

1. **V8 abstention threshold.** It assumed the cross-encoder returns logits and set the threshold to 0.0; V8 then never abstained (0% on skip jobs). The scores are sigmoid probabilities. Found from the measured abstention rate; fixed by calibrating on one persona and testing on the others (`evals/results/v8_threshold.json`).
2. **Requirement decomposition (V1).** The first merge fused ranks at chunk level and made retrieval *worse* than the baseline (MRR 0.42 vs 0.63). Fusing at project level helped recall but still did not beat hybrid+rerank. Both results are kept.
3. **Test isolation.** Tests shared one GigSim user whose Connects ran out, and a `.env` placeholder token leaked into unit tests; both surfaced as flaky failures and were fixed in the fixtures rather than by loosening assertions.
4. **Blocking the event loop.** The in-process toolbox ran CPU-bound retrieval inside `async` code, serialising "parallel" nodes; found because the fit matcher was slower than the sum of its parts.
5. **Rate limits.** It first launched evaluations without checking the provider's limits (8,000 tokens/min per model), which stalled them; a client-side token-bucket limiter was added and run sizes were reduced.
6. **Overlapping heavy jobs** (embedding evaluation + LLM evaluation + tracing server) exhausted RAM and got processes killed; evaluations now run strictly one at a time.
