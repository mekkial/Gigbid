"""Typed graph state (C2). Three things kept apart:
  * STATE (this object)  : what this job/conversation needs right now
  * TRACE (`trace` field + Langfuse/audit log): every node run, tokens, latency -- for audit/debug only
  * LONG-TERM MEMORY     : agent/memory/ (LangGraph store), written ONLY through promotion rules
Parallel branches write distinct keys; `steps`, `tokens`, `trace`, `errors`, `critiques` use additive reducers.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class BidState(TypedDict, total=False):
    # inputs
    job: dict[str, Any]
    user_id: str
    persona: str
    settings: dict[str, Any]          # floor_hourly, autonomy, ...
    # analyses (written by parallel branches)
    job_spec: dict[str, Any]
    risk_report: dict[str, Any]
    fit_report: dict[str, Any]
    evidence: list[dict[str, Any]]
    # decision / price / drafts
    decision: dict[str, Any]
    price_quote: dict[str, Any]
    draft: dict[str, Any]
    send_text: str                    # citation-stripped, compliance-cleaned text that would be sent
    claims: list[dict[str, Any]]
    unsupported_before: float
    unsupported_after: float
    critiques: Annotated[list[dict[str, Any]], operator.add]
    compliance: dict[str, Any]
    dry_run: dict[str, Any]
    approval: dict[str, Any]
    outcome: dict[str, Any]
    # control
    revision: int
    status: str                       # running|skipped|watch|awaiting_approval|submitted|rejected|blocked|needs_attention
    steps: Annotated[int, operator.add]
    tokens: Annotated[int, operator.add]
    cost_usd: Annotated[float, operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]


class ConvState(TypedDict, total=False):
    user_id: str
    persona: str
    proposal_id: str
    message: str
    intent: dict[str, Any]
    reply: dict[str, Any]
    approval: dict[str, Any]
    status: str
    steps: Annotated[int, operator.add]
    tokens: Annotated[int, operator.add]
    trace: Annotated[list[dict[str, Any]], operator.add]
