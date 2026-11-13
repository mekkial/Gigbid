# ADR 0002 — RAG hypotheses (written before the full evaluation)

Status: accepted · Date: 2026-11-13 · Evidence: `evals/results/rag_eval.json`

**Disclosure.** A 40-job smoke run of V0/V2/V3 (committed earlier as the first version of `rag_eval.json`) came before this note,
so H1 and H2 are partly informed by it. H3-H5 concern variants not yet run when this was written.

## Hypotheses
* **H1** Hybrid BM25+dense (V2) raises evidence Recall@5 over naive dense (V0) by >= 5 points, driven by exact tool names
  (e.g. "Hugging Face", "Stripe") that embeddings blur.
* **H2** Adding a cross-encoder reranker (V3) on top of V2 raises MRR by >= 0.10 and nDCG@10 by >= 0.05 at ~50x latency.
* **H3** Requirement decomposition (V1) beats V0 on jobs with four requirements (the "good" jobs) by >= 5 points of Recall@5,
  because a single embedding of a long post is dominated by one requirement.
* **H4** Outcome-aware boosting (V4) will NOT improve gold-evidence Recall@5/MRR, because gold evidence is defined by skills overlap,
  not by what won. It may still raise GigSim reply rate; that is measured separately. A flat result is an expected, reportable outcome.
* **H5** Corrective retrieval (V8) will abstain on most jobs that should be skipped (no gold evidence) at a cost of a few
  false abstentions on good jobs.

## Method
Dev set = 200 jobs per persona (synthetic gold labels, see DATA_CARD). Metrics at evidence (project) level: Recall@5, MRR, nDCG@10.
Broken down by persona and by job type (good / lowball / injection). Ablate the best pipeline one component at a time.
Caveat declared up front: the corpus is synthetic and templated, so absolute numbers are optimistic; relative ordering is the finding.
