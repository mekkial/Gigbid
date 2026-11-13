"""V3: hybrid candidates (top 30) re-scored by a cross-encoder for precision at small k."""
from rag.index.store import reranker
from rag.variants.v2_hybrid import rrf


def retrieve(job_query: str, index, k: int = 5, **_):
    cand = [i for i, _ in rrf([index.dense(job_query, 30), index.sparse(job_query, 30)])[:30]]
    scores = reranker().predict([(job_query, index.chunks[i]["text"]) for i in cand])
    order = sorted(zip(cand, scores), key=lambda x: -x[1])
    return [index.chunks[i] | {"score": float(s)} for i, s in order[:k]]
