"""V1: requirement decomposition: one dense retrieval per requirement, merged with RRF."""
from rag.variants.pipeline import retrieve_flags


def retrieve(q, index, k=5, **kw):
    return retrieve_flags(q, index, k, decompose=True, **kw)
