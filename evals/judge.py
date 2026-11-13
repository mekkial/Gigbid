"""LLM judge for proposals. Uses a DIFFERENT model family than the writer (avoids self-preference). Calibrated against human
labels in evals/runners/judge_calibration.py (Cohen's kappa); scores are only reported next to that kappa."""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent import llm
from agent.prompts import load_prompt, untrusted

JUDGE_MODEL = "qwen/qwen3.8-27b"


class JudgeScore(BaseModel):
    grounding: int = Field(ge=1, le=5)
    personalisation: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    acceptable: bool


def judge(job: dict, proposal: str, evidence: list[dict]) -> JudgeScore:
    ev = "\n".join(f"[{e['id']}] {e['text'][:300]}" for e in evidence) or "(none)"
    user = (f"JOB:\n{untrusted('job_post', job['title'] + chr(10) + job['description'])}\n\nEVIDENCE:\n{ev}\n\nPROPOSAL:\n{untrusted('proposal', proposal)}")
    with_override = dict(llm.OVERRIDES)
    llm.OVERRIDES["small"] = JUDGE_MODEL                      # 'verifier' node is on the small tier; judge reuses it with the judge model
    try:
        return llm.chat_json("verifier", load_prompt("judge"), user, JudgeScore)
    finally:
        llm.OVERRIDES.clear(); llm.OVERRIDES.update(with_override)
