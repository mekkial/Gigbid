"""V0 baseline: dense top-k cosine over the whole job post (the number everything must beat)."""
def retrieve(job_query: str, index, k: int = 5, **_):
    return [index.chunks[i] | {"score": s} for i, s in index.dense(job_query, k)]
