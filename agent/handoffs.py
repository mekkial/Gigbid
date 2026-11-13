"""Typed hand-offs between agents (C3). Anything a later step decides on is a Pydantic object, not text."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobSpec(BaseModel):
    job_id: str
    title: str
    deliverables: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    budget_type: Literal["fixed", "hourly", "unknown"] = "unknown"
    timeline: str | None = None
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)


class RiskReport(BaseModel):
    score: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list)  # unpaid_work, off_platform_contact, injection_attempt, ...
    client_quality: float = Field(ge=0, le=1, default=0.5)
    is_scam: bool = False
    injection_detected: bool = False
    explanation: str = ""


class RequirementMatch(BaseModel):
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)   # project ids
    supported: bool = False


class FitReport(BaseModel):
    score: float = Field(ge=0, le=1)
    matches: list[RequirementMatch] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasons: str = ""


class BidDecision(BaseModel):
    action: Literal["bid", "skip", "watch"]
    reason: str
    auto_skipped: bool = False


class PriceQuote(BaseModel):
    amount: float = Field(gt=0)
    budget_type: Literal["fixed", "hourly"] = "fixed"
    floor: float
    market_p50: float | None = None
    connects_cost: int = 0
    connects_worth_it: bool = True
    rationale: str


class Claim(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    verdict: Literal["supported", "partly_supported", "unsupported"] = "unsupported"


class ProposalDraft(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    revision: int = 0
    status: str = "pending_review"


class Critique(BaseModel):
    approved: bool
    grounding: float = Field(ge=0, le=1)
    personalisation: float = Field(ge=0, le=1)
    length_ok: bool = True
    issues: list[str] = Field(default_factory=list)


class ComplianceVerdict(BaseModel):
    allowed: bool
    violations: list[str] = Field(default_factory=list)
    cleaned_text: str = ""


class MessageIntent(BaseModel):
    intent: Literal["question", "negotiation", "interview_request", "scam_signal", "other"]
    confidence: float = Field(ge=0, le=1, default=0.5)


class ReplyDraft(BaseModel):
    proposal_id: str
    intent: MessageIntent
    text: str
    proposed_slots: list[str] = Field(default_factory=list)
