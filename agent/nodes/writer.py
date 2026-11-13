from pydantic import BaseModel, Field

from agent.handoffs import FitReport, JobSpec, PriceQuote, ProposalDraft
from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted


class _Out(BaseModel):
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


def write(job: dict, spec: JobSpec, fit: FitReport, price: PriceQuote, evidence: list[dict], style_rules: list[str],
          feedback: list[str] | None = None, revision: int = 0, defence: bool = True) -> ProposalDraft:
    ev = "\n".join(f"[evidence: {e['id']}] ({e['type']}, {e['date']}, outcome={e['outcome']}) {e['text'][:600]}" for e in evidence[:6]) or "(no evidence)"
    post = job['title'] + chr(10) + job['description']
    user = (f"{untrusted('job_post', post) if defence else post}\n\nSCREENING QUESTIONS: {spec.screening_questions}\n"
            f"BID: {price.amount} ({price.budget_type})\nEVIDENCE:\n{ev}\nSTYLE RULES: {style_rules or 'none'}\n"
            f"REVISION FEEDBACK: {feedback or 'none'}")
    system = load_prompt("writer")
    if not defence:                                   # ablation only: strip the SECURITY clause
        system = "\n".join(l for l in system.splitlines() if not l.startswith("SECURITY:"))
    o = chat_json("writer", system, user, _Out)
    return ProposalDraft(job_id=spec.job_id, cover_letter=o.cover_letter, screening_answers=o.screening_answers,
                         evidence_ids=o.evidence_ids, revision=revision)
