"""Factory: retrieval variant chosen by config (rag.variant), never hard-coded."""
from __future__ import annotations

import importlib

from agent.llm import load_config

VARIANTS = {"v0_naive": "rag.variants.v0_naive", "v2_hybrid": "rag.variants.v2_hybrid",
            "v3_rerank": "rag.variants.v3_rerank"}


def get_retriever(variant: str | None = None):
    variant = variant or load_config()["rag"]["variant"]
    return importlib.import_module(VARIANTS[variant]).retrieve


def job_query(job: dict) -> str:
    return f"{job['title']}. {job['description']} Skills: {', '.join(job['required_skills'])}"
