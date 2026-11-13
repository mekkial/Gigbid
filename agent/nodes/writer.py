from pydantic import BaseModel, Field

from agent.handoffs import FitReport, JobSpec, PriceQuote, ProposalDraft
from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted


class _Out(BaseModel):
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


def write(job: dict, spec: JobSpec, fit: FitReport, price: PriceQuote, evidence: list[dict], style_rules: list[str],
          feedback: list[str] | None = None, revision: int = 0) -> ProposalDraft:
    ev = "\n".join(f"[evidence: {e['id']}] ({e['type']}, {e['date']}, outcome={e['outcome']}) {e['text']}" for e in evidence) or "(no evidence)"
    user = (f"{untrusted('job_post', job['title'] + chr(10) + job['description'])}\n\nSCREENING QUESTIONS: {spec.screening_questions}\n"
            f"BID: {price.amount} ({price.budget_type})\nEVIDENCE:\n{ev}\nSTYLE RULES: {style_rules or 'none'}\n"
            f"REVISION FEEDBACK: {feedback or 'none'}")
    o = chat_json("writer", load_prompt("writer"), user, _Out)
    return ProposalDraft(job_id=spec.job_id, cover_letter=o.cover_letter, screening_answers=o.screening_answers,
                         evidence_ids=o.evidence_ids, revision=revision)
