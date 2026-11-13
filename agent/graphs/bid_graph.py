"""Bid graph (one thread per job). Hand-written StateGraph:

intake -> Send[ analyst | risk | fit ] (parallel) -> decide -> pricing -> writer -> verify -> critic
critic -(weak & revisions<2)-> writer ; critic -> compliance -> approval(interrupt) -> submit
Skip/watch/blocked/needs_attention end early with a visible status. Nothing is sent before human approval.
"""
from __future__ import annotations

import asyncio
import difflib
import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send, interrupt

from agent.handoffs import BidDecision, ComplianceVerdict, Critique, FitReport, JobSpec, PriceQuote, ProposalDraft, RiskReport
from agent.llm import USAGE, cost_usd, load_config
from agent.memory import promotion_rules as mem
from agent.nodes import analyst, compliance, critic, fit_matcher, pricing, risk_assessor, writer
from agent.state import BidState
from rag import verify as ver


@dataclass
class Impl:
    """Node implementations; tests/evals override these (e.g. offline stubs, ablations, single-agent baselines)."""
    analyse: Callable = analyst.analyse
    assess: Callable = risk_assessor.assess
    match: Callable = fit_matcher.match
    quote: Callable = pricing.quote
    write: Callable = writer.write
    verify_claims: Callable = ver.verify_claims
    review: Callable = critic.review
    check: Callable = compliance.check
    flags: dict = field(default_factory=lambda: {"injection_defence": True})


def _tracked(name: str):
    """Wrap a node: step counter, token/cost accounting, latency trace, budget guard (C4), error capture."""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(state: BidState, config=None):
            cfg = load_config()["budgets"]
            if state.get("steps", 0) >= cfg["max_graph_steps"] or state.get("tokens", 0) >= cfg["max_tokens_per_job"]:
                return {"status": "needs_attention", "errors": [f"budget exceeded before {name}"]}
            usage: list = []
            tok = USAGE.set(usage)
            t0 = time.time()
            try:
                out = fn(state, config) if config is not None else fn(state)
                if asyncio.iscoroutine(out):
                    out = await out
            finally:
                USAGE.reset(tok)
            tin = sum(u[1] for u in usage); tout = sum(u[2] for u in usage)
            c = sum(cost_usd(m, a, b) for m, a, b in usage)
            out = dict(out or {})
            out["steps"] = 1
            out["tokens"] = tin + tout
            out["cost_usd"] = c
            out["trace"] = [{"node": name, "latency_s": round(time.time() - t0, 3), "tokens_in": tin, "tokens_out": tout,
                             "cost_usd": round(c, 6), "models": sorted({m for m, _, _ in usage})}]
            return out
        return wrapper
    return deco


def build_bid_graph(tools, store, checkpointer=None, impl: Impl | None = None):
    impl = impl or Impl()
    cfg = load_config()
    max_rev = cfg["budgets"]["max_revisions"]
    th = cfg["thresholds"]

    async def intake(state: BidState):
        return {"status": "running", "revision": 0}

    def fan_out(state: BidState):
        return [Send("analyst", state), Send("risk", state), Send("fit", state)]

    @_tracked("analyst")
    async def n_analyst(state):
        return {"job_spec": (await asyncio.to_thread(impl.analyse, state["job"])).model_dump()}

    @_tracked("risk_assessor")
    async def n_risk(state):
        r = await impl.assess(tools, state["job"], injection_defence=impl.flags.get("injection_defence", True))
        return {"risk_report": r.model_dump()}

    @_tracked("fit_matcher")
    async def n_fit(state):
        spec = analyst.deterministic_spec(state["job"])      # runs in parallel with the analyst: uses structured fields
        fit, ev = await impl.match(tools, spec)
        return {"fit_report": fit.model_dump(), "evidence": ev}

    @_tracked("decide")
    async def decide(state):
        risk, fit = RiskReport(**state["risk_report"]), FitReport(**state["fit_report"])
        auto = state.get("settings", {}).get("autonomy", cfg["autonomy"]["default"]) == "auto_skip_low_fit"
        if risk.is_scam:
            d = BidDecision(action="skip", reason=f"scam signals: {risk.flags}", auto_skipped=True)
        elif risk.score > th["maximum_risk_score"]:
            d = BidDecision(action="skip", reason=f"risk {risk.score:.2f} above {th['maximum_risk_score']}")
        elif fit.score < th["minimum_fit_score"]:
            d = BidDecision(action="skip", reason=f"fit {fit.score:.2f} below {th['minimum_fit_score']}; missing {fit.missing_skills}",
                            auto_skipped=auto)
        else:
            d = BidDecision(action="bid", reason=f"fit {fit.score:.2f}, risk {risk.score:.2f}")
        return {"decision": d.model_dump(), "status": "skipped" if d.action == "skip" else "running"}

    def after_decide(state):
        if state.get("status") == "needs_attention":
            return END
        return "pricing" if state["decision"]["action"] == "bid" else END

    @_tracked("pricing")
    async def n_pricing(state):
        spec, fit, risk = JobSpec(**state["job_spec"]), FitReport(**state["fit_report"]), RiskReport(**state["risk_report"])
        hint = mem.win_prob_hint(store, state["user_id"], state["job"].get("persona_hint", "general"))
        q = await impl.quote(tools, spec, fit, risk, state.get("settings", {}).get("floor_hourly", 30),
                             state["job"].get("connects_cost", 8), hint)
        upd = {"price_quote": q.model_dump()}
        if not q.connects_worth_it:
            upd["decision"] = BidDecision(action="watch", reason="Connects cost not worth the expected value").model_dump()
            upd["status"] = "watch"
        return upd

    def after_pricing(state):
        return END if state.get("status") in ("watch", "needs_attention") else "writer"

    @_tracked("writer")
    async def n_writer(state):
        rev = state.get("revision", 0)
        crit = state.get("critiques") or []
        fb = crit[-1]["issues"] if crit and rev > 0 else None
        d = await asyncio.to_thread(
            impl.write, state["job"], JobSpec(**state["job_spec"]), FitReport(**state["fit_report"]),
            PriceQuote(**state["price_quote"]), state["evidence"], mem.style_rules(store, state["user_id"]), fb, rev)
        return {"draft": d.model_dump()}

    @_tracked("verifier")
    async def n_verify(state):
        d = ProposalDraft(**state["draft"])
        claims = await asyncio.to_thread(impl.verify_claims, d.cover_letter, state["evidence"])
        before = ver.unsupported_rate(claims)
        d.cover_letter = ver.remove_unsupported(d.cover_letter, claims)
        after_claims = await asyncio.to_thread(impl.verify_claims, d.cover_letter, state["evidence"]) if before > 0 else claims
        d.claims = [c for c in after_claims]
        return {"draft": d.model_dump(), "claims": [c.model_dump() for c in d.claims],
                "unsupported_before": before, "unsupported_after": ver.unsupported_rate(after_claims)}

    @_tracked("critic")
    async def n_critic(state):
        d = ProposalDraft(**state["draft"])
        n_bad = sum(c["verdict"] == "unsupported" for c in state.get("claims", []))
        c = await asyncio.to_thread(impl.review, state["job"], d, n_bad)
        return {"critiques": [c.model_dump()], "revision": state.get("revision", 0) + (0 if c.approved else 1)}

    def after_critic(state):
        c = state["critiques"][-1]
        if c["approved"] or state.get("revision", 0) > max_rev:
            return "compliance"
        return "writer"

    @_tracked("compliance")
    async def n_compliance(state):
        d = ProposalDraft(**state["draft"])
        from agent.nodes.compliance import strip_citations
        v = impl.check(strip_citations(d.cover_letter))
        upd: dict[str, Any] = {"compliance": v.model_dump(), "send_text": v.cleaned_text}
        if not v.allowed:
            upd["status"] = "blocked"
        return upd

    def after_compliance(state):
        return END if state.get("status") == "blocked" else "approval"

    async def approval(state: BidState, config):
        """Human gate (R4/C5): interrupt() pauses the thread; the UI resumes it with approve|edit|reject."""
        d = ProposalDraft(**state["draft"])
        payload = {"kind": "proposal_approval", "job_id": state["job"]["job_id"], "draft": d.cover_letter,
                   "send_text": state["send_text"], "claims": state.get("claims", []), "evidence": state["evidence"],
                   "risk_report": state["risk_report"], "price_quote": state["price_quote"],
                   "critiques": state.get("critiques", []), "compliance": state["compliance"],
                   "dry_run": await tools.call("submit", "create_proposal_draft", dry_run=True, idempotency_key="preview-dry-run",
                                               payload={"job_id": state["job"]["job_id"], "cover_letter": state["send_text"],
                                                        "bid_amount": state["price_quote"]["amount"]})}
        resp = interrupt(payload)
        action = resp.get("action")
        if action == "reject":
            return {"approval": resp, "status": "rejected", "steps": 1}
        text = state["send_text"]
        if action == "edit":
            edited = resp["text"]
            v = impl.check(edited)                                   # edits are re-checked by Compliance
            promoted = mem.record_edit(store, state["user_id"], state["job"]["job_id"], text, edited)
            diff = "\n".join(difflib.unified_diff(text.split(". "), edited.split(". "), lineterm=""))
            if not v.allowed:
                return {"approval": {**resp, "diff": diff, "violations": v.violations}, "status": "blocked", "steps": 1}
            return {"approval": {**resp, "diff": diff, "promoted_style_rules": promoted, "violations": v.violations},
                    "send_text": v.cleaned_text, "status": "approved", "steps": 1}
        return {"approval": resp, "status": "approved", "steps": 1}

    def after_approval(state):
        return "submit" if state.get("status") == "approved" else END

    async def submit(state: BidState, config):
        tid = config["configurable"]["thread_id"]
        payload = {"job_id": state["job"]["job_id"], "cover_letter": state["send_text"], "bid_amount": state["price_quote"]["amount"]}
        # idempotency keys derive from the thread id: a retry/restart can never submit or spend Connects twice
        prop = await tools.call("submit", "create_proposal_draft", payload=payload, idempotency_key=f"{tid}:create")
        res = await tools.call("submit", "submit_proposal", proposal_id=prop["proposal_id"], idempotency_key=f"{tid}:submit")
        return {"outcome": res, "status": "submitted", "steps": 1}

    g = StateGraph(BidState)
    retry = RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0)
    for name, fn in [("intake", intake), ("analyst", n_analyst), ("risk", n_risk), ("fit", n_fit), ("decide", decide),
                     ("pricing", n_pricing), ("writer", n_writer), ("verify", n_verify), ("critic", n_critic),
                     ("compliance", n_compliance)]:
        g.add_node(name, fn, retry_policy=retry if name not in ("intake",) else None)
    g.add_node("approval", approval)
    g.add_node("submit", submit, retry_policy=retry)
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", fan_out, ["analyst", "risk", "fit"])
    g.add_edge(["analyst", "risk", "fit"], "decide")
    g.add_conditional_edges("decide", after_decide, ["pricing", END])
    g.add_conditional_edges("pricing", after_pricing, ["writer", END])
    g.add_edge("writer", "verify")
    g.add_edge("verify", "critic")
    g.add_conditional_edges("critic", after_critic, ["writer", "compliance"])
    g.add_conditional_edges("compliance", after_compliance, ["approval", END])
    g.add_conditional_edges("approval", after_approval, ["submit", END])
    g.add_edge("submit", END)
    return g.compile(checkpointer=checkpointer)


def build_bid_graph_default():
    raise RuntimeError("use build_bid_graph(tools, store, checkpointer)")
