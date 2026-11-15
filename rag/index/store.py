"""Dense + BM25 index over chunks. Embeddings and reranker are open models running on CPU."""
from __future__ import annotations

import os
import re
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from agent.llm import load_config


@lru_cache(maxsize=1)
def embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(load_config()["models"]["embeddings"], device=os.environ.get("GIGBID_DEVICE", "cpu"))   # open models on CPU (reproducible, no GPU needed)


@lru_cache(maxsize=1)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(load_config()["models"]["reranker"], device=os.environ.get("GIGBID_DEVICE", "cpu"))


def tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]+", s.lower())


class Index:
    def __init__(self, chunks: list[dict], dense: bool | None = None):
        """dense=None: build embeddings unless the active variant is BM25-only (the 512 MB deployment never loads a model)."""
        from rag.retriever import active_variant
        self.chunks = chunks
        self.use_dense = (active_variant() != "v6_bm25") if dense is None else dense
        self.emb = embedder().encode([c["text"] for c in chunks], normalize_embeddings=True, show_progress_bar=False) if self.use_dense else None
        self.bm25 = BM25Okapi([tok(c["text"] + " " + " ".join(c["skills"])) for c in chunks])

    def dense(self, query: str, n: int = 30) -> list[tuple[int, float]]:
        if self.emb is None:
            raise RuntimeError("dense retrieval is disabled (BM25-only index); unset RAG_VARIANT=v6_bm25 to use the embedding variants")
        q = embedder().encode([query], normalize_embeddings=True)[0]
        sims = self.emb @ q
        top = np.argsort(-sims)[:n]
        return [(int(i), float(sims[i])) for i in top]

    def sparse(self, query: str, n: int = 30) -> list[tuple[int, float]]:
        s = self.bm25.get_scores(tok(query))
        top = np.argsort(-s)[:n]
        return [(int(i), float(s[i])) for i in top]

    def add(self, new_chunks: list[dict]) -> None:
        """Incremental re-index (B1): embed only the new chunks and append; BM25 is rebuilt over the corpus (cheap)."""
        ids = {c["chunk_id"] for c in self.chunks}
        new = [c for c in new_chunks if c["chunk_id"] not in ids]
        if not new:
            return
        if self.emb is not None:
            self.emb = np.vstack([self.emb, embedder().encode([c["text"] for c in new], normalize_embeddings=True, show_progress_bar=False)])
        self.chunks = self.chunks + new
        self.bm25 = BM25Okapi([tok(c["text"] + " " + " ".join(c["skills"])) for c in self.chunks])
