"""Claim verification (B3): split a proposal into claims, grade each against evidence, drop unsupported ones."""
from __future__ import annotations

import re

from pydantic import BaseModel

from agent.handoffs import Claim
from agent.llm import chat_json
from agent.prompts import load_prompt


class _Claims(BaseModel):
    claims: list[Claim]


def _evidence_block(evidence: list[dict]) -> str:
    return "\n".join(f"[{e['id']}] ({e['type']}, {e['date']}) {e['text']}" for e in evidence) or "(none)"


def verify_claims(draft: str, evidence: list[dict]) -> list[Claim]:
    out = chat_json("verifier", load_prompt("verifier"),
                    f"EVIDENCE:\n{_evidence_block(evidence)}\n\nPROPOSAL:\n{draft}", _Claims)
    return out.claims


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _overlap(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def remove_unsupported(draft: str, claims: list[Claim]) -> str:
    bad = [c for c in claims if c.verdict == "unsupported"]
    keep = [s for s in _sentences(draft) if not any(_overlap(s, c.text) >= 0.6 for c in bad)]
    return " ".join(keep)


def unsupported_rate(claims: list[Claim]) -> float:
    return sum(c.verdict == "unsupported" for c in claims) / len(claims) if claims else 0.0
