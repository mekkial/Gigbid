"""The bid / skip / watch rule, shared by the bid graph and the decision evaluation (single source of truth)."""
from agent.handoffs import BidDecision, FitReport, RiskReport
from agent.llm import load_config


def decide(risk: RiskReport, fit: FitReport, autonomy: str | None = None) -> BidDecision:
    cfg = load_config()
    th = cfg["thresholds"]
    auto = (autonomy or cfg["autonomy"]["default"]) == "auto_skip_low_fit"
    if risk.is_scam:
        return BidDecision(action="skip", reason=f"scam signals: {risk.flags}", auto_skipped=True)
    if risk.score > th["maximum_risk_score"]:
        return BidDecision(action="skip", reason=f"risk {risk.score:.2f} above {th['maximum_risk_score']}")
    if fit.score < th["minimum_fit_score"]:
        return BidDecision(action="skip", reason=f"fit {fit.score:.2f} below {th['minimum_fit_score']}; missing {fit.missing_skills}", auto_skipped=auto)
    return BidDecision(action="bid", reason=f"fit {fit.score:.2f}, risk {risk.score:.2f}")
