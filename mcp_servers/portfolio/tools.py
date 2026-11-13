"""Portfolio MCP tools (read-only). Backed by the persona corpus + the configured RAG variant."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


class EvidenceItem(BaseModel):
    id: str = Field(description="Project/evidence id; usable with get_case_study and portfolio://case/{id}")
    type: str = Field(description="case_study | readme | code | review | proposal | cv")
    source: str
    date: str
    outcome: str | None = Field(default=None, description="won | replied | ignored (proposals only)")
    skills: list[str]
    text: str


class CaseStudy(BaseModel):
    id: str
    title: str
    skills: list[str]
    industry: str
    year: int
    case_study: str
    readme: str


class Filters(BaseModel):
    type: str | None = Field(default=None, description="restrict to one evidence type")
    skill: str | None = Field(default=None, description="restrict to items that list this skill")
    industry: str | None = None
    outcome: str | None = Field(default=None, description="won | replied | ignored")


@lru_cache(maxsize=1)
def _state():
    from rag.index.store import Index
    from rag.ingest.loaders import load_persona
    from rag.retriever import get_retriever

    persona = os.environ.get("GIGBID_PERSONA", "ai_ml")
    base = Path(os.environ.get("GIGBID_PORTFOLIO_DIR", ROOT / "data" / "personas"))
    chunks = load_persona(persona, base)
    cases = {c["id"]: c for c in json.loads((base / persona / "case_studies.json").read_text())}
    props = {}
    for line in (base / persona / "proposals.jsonl").read_text().splitlines():
        p = json.loads(line); props[p["id"]] = p
    return {"persona": persona, "index": Index(chunks), "retrieve": get_retriever(), "cases": cases, "proposals": props,
            "profile": json.loads((base / persona / "profile.json").read_text())}


def search_evidence(requirement: str, k: int = 5, filters: Filters | None = None) -> list[EvidenceItem]:
    s = _state()
    f = filters or Filters()
    seen, out = set(), []
    for c in s["retrieve"](requirement, s["index"], k=50):
        if c["project"] == "cv" or c["project"] in seen:
            continue
        if f.type and c["type"] != f.type: continue
        if f.skill and f.skill.lower() not in [x.lower() for x in c["skills"]]: continue
        if f.industry and c.get("client_industry") != f.industry: continue
        if f.outcome and c.get("outcome") != f.outcome: continue
        seen.add(c["project"])
        out.append(EvidenceItem(id=c["project"], type=c["type"], source=f"{c['type']}:{c['project']}", date=c["date"],
                                outcome=c.get("outcome"), skills=c["skills"], text=c["text"][:900]))
        if len(out) >= k:
            break
    return out


def get_case_study(id: str) -> CaseStudy:
    c = _state()["cases"].get(id)
    if not c:
        raise ValueError(f"unknown case study '{id}'")
    return CaseStudy(id=c["id"], title=c["title"], skills=c["skills"], industry=c["industry"], year=c["year"],
                     case_study=c["case_study_md"], readme=c["readme_md"])


def list_skills() -> list[str]:
    s = _state()
    return sorted(set(s["profile"]["skills"]) | {x for c in s["cases"].values() for x in c["skills"]})
