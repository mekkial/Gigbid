"""Load a persona corpus into metadata-rich chunks (B1). Every chunk carries:
persona, type, project, skills, date, client_industry and (for proposals) outcome."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_CHARS = 700


def _split(text: str, n: int = MAX_CHARS) -> list[str]:
    parts, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > n and cur:
            parts.append(cur.strip()); cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _chunk(persona, ctype, project, skills, date, industry, text, outcome=None, idx=0):
    cid = hashlib.sha1(f"{persona}|{ctype}|{project}|{idx}|{text[:60]}".encode()).hexdigest()[:12]
    return {"chunk_id": cid, "persona": persona, "type": ctype, "project": project, "skills": skills,
            "date": date, "client_industry": industry, "outcome": outcome, "text": text}


def load_persona(persona: str, base: Path | None = None) -> list[dict]:
    base = (base or ROOT / "data" / "personas") / persona
    cases = json.loads((base / "case_studies.json").read_text())
    by_id = {c["id"]: c for c in cases}
    chunks = []
    for c in cases:
        date = f"{c['year']}-06-01"
        for i, t in enumerate(_split(c["case_study_md"])):
            chunks.append(_chunk(persona, "case_study", c["id"], c["skills"], date, c["industry"], t, idx=i))
        chunks.append(_chunk(persona, "readme", c["id"], c["skills"], date, c["industry"], c["readme_md"]))
        chunks.append(_chunk(persona, "code", c["id"], c["skills"], date, c["industry"], c["code_snippet"]))
    for line in (base / "reviews.jsonl").read_text().splitlines():
        r = json.loads(line); c = by_id.get(r["project"], {})
        chunks.append(_chunk(persona, "review", r["project"], c.get("skills", []), f"{c.get('year', 2024)}-07-01",
                             c.get("industry"), r["text"]))
    for line in (base / "proposals.jsonl").read_text().splitlines():
        p = json.loads(line); c = by_id.get(p["project"], {})
        chunks.append(_chunk(persona, "proposal", p["project"], p["skills"], f"{c.get('year', 2024)}-08-01",
                             c.get("industry"), p["text"], outcome=p["outcome"]))
    cv = (base / "cv.md").read_text()
    chunks.append(_chunk(persona, "cv", "cv", json.loads((base / "profile.json").read_text())["skills"], "2025-01-01", None, cv))
    return chunks
