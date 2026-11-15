"""Factory: retrieval variant chosen by config (rag.variant), never hard-coded."""
from __future__ import annotations

import importlib
import os

from agent.llm import load_config

VARIANTS = {"v0_naive": "rag.variants.v0_naive", "v1_decompose": "rag.variants.v1_decompose", "v2_hybrid": "rag.variants.v2_hybrid",
            "v3_rerank": "rag.variants.v3_rerank", "v4_outcome": "rag.variants.v4_outcome", "v5_full": "rag.variants.v5_full",
            "v8_corrective": "rag.variants.v8_corrective", "v6_bm25": "rag.variants.v6_bm25"}


def active_variant() -> str:
    """The configured retrieval variant. The RAG_VARIANT environment variable overrides it (used by the light deployment)."""
    return os.environ.get("RAG_VARIANT") or load_config()["rag"]["variant"]


def get_retriever(variant: str | None = None):
    variant = variant or active_variant()
    return importlib.import_module(VARIANTS[variant]).retrieve


def job_query(job: dict) -> str:
    return f"{job['title']}. {job['description']} Skills: {', '.join(job['required_skills'])}"
