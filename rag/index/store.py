"""Dense + BM25 index over chunks. Embeddings and reranker are open models running on CPU."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from agent.llm import load_config


@lru_cache(maxsize=1)
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(load_config()["models"]["embeddings"])


@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(load_config()["models"]["reranker"])


def tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", s.lower())


class Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.emb = embedder().encode([c["text"] for c in chunks], normalize_embeddings=True, show_progress_bar=False)
        self.bm25 = BM25Okapi([tok(c["text"] + " " + " ".join(c["skills"])) for c in chunks])

    def dense(self, query: str, n: int = 30) -> list[tuple[int, float]]:
        q = embedder().encode([query], normalize_embeddings=True)[0]
        sims = self.emb @ q
        top = np.argsort(-sims)[:n]
        return [(int(i), float(sims[i])) for i in top]

    def sparse(self, query: str, n: int = 30) -> list[tuple[int, float]]:
        s = self.bm25.get_scores(tok(query))
        top = np.argsort(-s)[:n]
        return [(int(i), float(s[i])) for i in top]
