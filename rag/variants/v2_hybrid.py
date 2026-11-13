"""V2: BM25 + dense fused with reciprocal rank fusion (catches exact tool names embeddings blur)."""
def rrf(rank_lists, k=60):
    sc = {}
    for rl in rank_lists:
        for r, (i, _) in enumerate(rl):
            sc[i] = sc.get(i, 0) + 1 / (k + r + 1)
    return sorted(sc.items(), key=lambda x: -x[1])


def retrieve(job_query: str, index, k: int = 5, **_):
    fused = rrf([index.dense(job_query, 30), index.sparse(job_query, 30)])
    return [index.chunks[i] | {"score": s} for i, s in fused[:k]]
