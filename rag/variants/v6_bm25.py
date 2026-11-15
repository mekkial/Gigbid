"""V6: BM25 keyword search only. Needs no embedding model and no reranker, so it runs in about 100 MB: this is the variant the
512 MB free-host deployment uses (RAG_VARIANT=v6_bm25). It is evaluated like every other variant (evals/results/rag_eval.json)."""


def retrieve(job_query: str, index, k: int = 5, **_):
    return [index.chunks[i] | {"score": s} for i, s in index.sparse(job_query, k)]
