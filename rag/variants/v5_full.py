"""Full composed pipeline (decompose + hybrid + rerank + outcome) used as the base for ablation."""
from rag.variants.pipeline import retrieve_flags


def retrieve(q, index, k=5, **kw):
    return retrieve_flags(q, index, k, decompose=True, sparse=True, rerank=True, outcome=True, **kw)
