"""Composable retrieval pipeline. Every variant is a configuration of these switches, which also makes ablation trivial:
  decompose : one retrieval per job requirement, results merged with RRF   (V1)
  sparse    : add BM25 to dense with reciprocal rank fusion                (V2)
  rerank    : cross-encoder re-scoring of candidates                       (V3)
  outcome   : boost evidence from projects whose proposals won/replied     (V4)
"""
from __future__ import annotations

import re
from collections import defaultdict

from agent.llm import load_config
from rag.index.store import reranker


def rrf(lists: list[list[int]], k: int = 60) -> dict[int, float]:
    sc: dict[int, float] = defaultdict(float)
    for lst in lists:
        for r, i in enumerate(lst):
            sc[i] += 1.0 / (k + r + 1)
    return sc


def requirements_from_query(q: str) -> list[str]:
    m = re.search(r"Skills:\s*(.+)$", q.strip(), re.S)
    return [s.strip() for s in m.group(1).split(",") if s.strip()] if m else []


def project_success(index) -> dict[str, float]:
    """Outcome signal per project: (won + 0.5*replied) / proposals, computed once from the labelled past proposals."""
    if not hasattr(index, "_succ"):
        n, w = defaultdict(int), defaultdict(float)
        for c in index.chunks:
            if c["type"] == "proposal":
                p = c["project"].removesuffix("-v2"); n[p] += 1
                w[p] += 1.0 if c["outcome"] == "won" else 0.5 if c["outcome"] == "replied" else 0.0
        index._succ = {p: w[p] / n[p] for p in n}
    return index._succ


def rerank_scores(index, q: str, ids: list[int]) -> list[float]:
    """Cross-encoder scores with a per-index cache (variants and ablations re-score the same (query, chunk) pairs)."""
    cache = index.__dict__.setdefault("_rr_cache", {})
    todo = [i for i in ids if (q, i) not in cache]
    if todo:
        for i, sc in zip(todo, reranker().predict([(q, index.chunks[i]["text"]) for i in todo])):
            cache[(q, i)] = float(sc)
    return [cache[(q, i)] for i in ids]


def retrieve_flags(query: str, index, k: int = 5, *, decompose=False, sparse=False, rerank=False, outcome=False,
                   pool: int = 30, requirements: list[str] | None = None, project_level_fusion: bool = True, **_) -> list[dict]:
    queries = [query]
    if decompose:
        reqs = requirements or requirements_from_query(query)
        title = query.split(".")[0]
        queries = [f"{r} - {title}" for r in reqs] or [query]
    ranked_lists = []
    for q in queries:
        cand = [i for i, _ in index.dense(q, pool)]
        lists = [cand]
        if sparse:
            lists.append([i for i, _ in index.sparse(q, pool)])
        fused = rrf(lists)
        order = [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])][:pool]
        if rerank:
            s = rerank_scores(index, q, order)
            order = [i for i, _ in sorted(zip(order, s), key=lambda x: -x[1])]
        ranked_lists.append(order)
    if decompose and len(ranked_lists) > 1 and project_level_fusion:
        # Merge per-requirement rankings at PROJECT level: a project that satisfies several requirements appears in several lists
        # and accumulates RRF score. (Chunk-level merging scatters a project's chunks across lists; it measured worse, see
        # evals/results/rag_eval_v1_chunk_level_fusion.json.)
        proj_lists, rep = [], {}
        for order in ranked_lists:
            seen = []
            for i in order:
                p = index.chunks[i]["project"].removesuffix("-v2")
                if p not in seen:
                    seen.append(p); rep.setdefault(p, i)
            proj_lists.append(seen)
        pscore: dict = defaultdict(float)
        for lst in proj_lists:
            for r, p in enumerate(lst):
                pscore[p] += 1.0 / (60 + r + 1)
        if outcome:
            lam = load_config()["rag"].get("outcome_boost", 1.0); succ = project_success(index)
            pscore = {p: sc * (1 + lam * succ.get(p, 0.0)) for p, sc in pscore.items()}
        top = sorted(pscore.items(), key=lambda x: -x[1])[:k]
        return [index.chunks[rep[p]] | {"score": sc} for p, sc in top]
    final = rrf(ranked_lists) if len(ranked_lists) > 1 else {i: 1.0 / (r + 1) for r, i in enumerate(ranked_lists[0])}
    if outcome:
        lam = load_config()["rag"].get("outcome_boost", 1.0)
        succ = project_success(index)
        final = {i: s * (1 + lam * succ.get(index.chunks[i]["project"].removesuffix("-v2"), 0.0)) for i, s in final.items()}
    top = sorted(final.items(), key=lambda x: -x[1])[:k]
    return [index.chunks[i] | {"score": s} for i, s in top]
