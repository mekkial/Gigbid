"""V4: hybrid retrieval + outcome-aware boost (evidence from projects behind winning proposals ranks higher)."""
from rag.variants.pipeline import retrieve_flags


def retrieve(q, index, k=5, **kw):
    return retrieve_flags(q, index, k, sparse=True, outcome=True, **kw)
