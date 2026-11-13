"""Request/response models. The TypeScript client in apps/web/src/lib/api is generated from these via OpenAPI."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Persona = Literal["ai_ml", "fullstack", "data_analyst"]


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    persona: Persona = "ai_ml"


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Settings(BaseModel):
    floor_hourly: float = Field(default=30, gt=0, le=1000)
    weekly_connects_budget: int = Field(default=100, ge=0, le=2000)
    autonomy: Literal["manual", "auto_skip_low_fit"] = "manual"
    marketplace_mode: Literal["gigsim", "upwork_live"] = "gigsim"
    keywords: list[str] = Field(default_factory=list)
    min_budget: float = 0


class UserOut(BaseModel):
    id: str
    email: str
    persona: Persona
    settings: Settings
    connected: list[str] = Field(default_factory=list)


class SettingsIn(BaseModel):
    persona: Persona | None = None
    settings: Settings | None = None


class SavedSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    interval_min: int = Field(default=180, ge=60, le=1440)        # polite: never faster than hourly


class SavedSearchOut(SavedSearchIn):
    id: int


class ScoutIn(BaseModel):
    query: str = Field(default="", max_length=200)
    limit: int = Field(default=10, ge=1, le=30)


class RunOut(BaseModel):
    thread_id: str
    job_id: str
    kind: str = "bid"
    status: str
    title: str | None = None
    category: str | None = None
    fit: float | None = None
    risk: float | None = None
    decision: str | None = None
    price: float | None = None
    connects: int | None = None
    tokens: int = 0
    cost_usd: float = 0
    latency_s: float = 0
    proposal_id: str | None = None
    outcome: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DecisionIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    text: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=500)
    slot: str | None = None


class RegenerateIn(BaseModel):
    paragraph_index: int = Field(ge=0, le=20)
    instruction: str | None = Field(default=None, max_length=300)


class RegenerateOut(BaseModel):
    text: str


class PortfolioUploadOut(BaseModel):
    item_id: str
    chunks: int


class MemoryItem(BaseModel):
    namespace: str
    key: str
    value: dict[str, Any]


class PipelineCard(BaseModel):
    thread_id: str
    job_id: str
    title: str | None
    stage: Literal["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]
    price: float | None = None
    proposal_id: str | None = None


class AnalyticsOut(BaseModel):
    totals: dict[str, Any]
    by_category: list[dict[str, Any]]
    connects: dict[str, Any]
    cost_latency: dict[str, Any]
    rejection_reasons: list[dict[str, Any]]
