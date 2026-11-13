"""V8 corrective retrieval (a small LangGraph-style loop): retrieve -> grade each item -> re-query if weak -> refuse if none.

Grader = cross-encoder relevance PROBABILITY against the requirements (threshold in config: rag.v8_threshold). An a-priori threshold of 0.0
(assuming logits) never abstained because CrossEncoder returns sigmoid probabilities; the shipped value is calibrated on ONE persona
and verified on the others (evals/results/v8_threshold.json). If nothing passes, the query is rewritten to the bare requirement list
and tried once more; if still nothing passes the retriever returns [] meaning "refuse to claim experience".
"""
from agent.llm import load_config
from rag.variants.pipeline import requirements_from_query, rerank_scores, retrieve_flags


def _grade(query, cands, thr):
    if not cands:
        return []
    ids = [c["_i"] for c in cands]
    s = rerank_scores(cands[0]["_index"], query, ids)
    return [{k: v for k, v in c.items() if k not in ("_i", "_index")} | {"grade": x} for c, x in zip(cands, s) if x > thr]


def _cands(q, index):
    pos = {c["chunk_id"]: i for i, c in enumerate(index.chunks)}
    return [c | {"_i": pos[c["chunk_id"]], "_index": index} for c in retrieve_flags(q, index, 30, sparse=True, rerank=True)]


def retrieve(q, index, k=5, **kw):
    thr = load_config()["rag"].get("v8_threshold", 0.0)
    reqs = requirements_from_query(q)
    good = _grade(q, _cands(q, index), thr)
    if not good and reqs:                                         # corrective step: rewrite query to the requirement list
        q2 = "Experience with " + ", ".join(reqs)
        good = _grade(q2, _cands(q2, index), thr)
    return sorted(good, key=lambda c: -c["grade"])[:k]            # [] == refuse to claim
