"""The bid / skip / watch rule, shared by the bid graph and the decision evaluation (single source of truth)."""
from agent.handoffs import BidDecision, FitReport, RiskReport
from agent.llm import load_config


def budget_below_floor(job: dict | None, floor_hourly: float | None) -> str | None:
    """Deterministic: a posted budget that cannot reach the freelancer's own rate floor is not worth a bid (and Connects)."""
    if not job or not floor_hourly:
        return None
    b = job.get("budget") or {}
    hi = b.get("max") or 0
    if b.get("type") == "hourly":
        return f"max hourly rate {hi:g} is below your floor {floor_hourly:g}" if 0 < hi < floor_hourly else None
    need = floor_hourly * load_config()["thresholds"].get("min_fixed_hours", 8)
    return f"fixed budget {hi:g} is below your minimum {need:g} ({floor_hourly:g}/h x {load_config()['thresholds'].get('min_fixed_hours', 8)}h)" if 0 < hi < need else None


def decide(risk: RiskReport, fit: FitReport, autonomy: str | None = None, job: dict | None = None, floor_hourly: float | None = None) -> BidDecision:
    cfg = load_config()
    th = cfg["thresholds"]
    auto = (autonomy or cfg["autonomy"]["default"]) == "auto_skip_low_fit"
    if risk.is_scam:
        return BidDecision(action="skip", reason=f"scam signals: {risk.flags}", auto_skipped=True)
    low = budget_below_floor(job, floor_hourly)
    if low:
        return BidDecision(action="skip", reason=low)
    if risk.score > th["maximum_risk_score"]:
        return BidDecision(action="skip", reason=f"risk {risk.score:.2f} above {th['maximum_risk_score']}")
    if fit.score < th["minimum_fit_score"]:
        return BidDecision(action="skip", reason=f"fit {fit.score:.2f} below {th['minimum_fit_score']}; missing {fit.missing_skills}", auto_skipped=auto)
    return BidDecision(action="bid", reason=f"fit {fit.score:.2f}, risk {risk.score:.2f}")
