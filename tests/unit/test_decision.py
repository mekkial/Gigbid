from agent.handoffs import FitReport, RiskReport
from agent.nodes.decision import budget_below_floor, decide

GOOD_FIT, LOW_RISK = FitReport(score=1.0), RiskReport(score=0.1)


def test_lowball_fixed_budget_is_skipped_but_a_fair_one_is_bid():
    cheap = {"budget": {"min": 5, "max": 20}}
    fair = {"budget": {"min": 800, "max": 1600}}
    assert decide(LOW_RISK, GOOD_FIT, None, cheap, 30).action == "skip" and "below your minimum" in decide(LOW_RISK, GOOD_FIT, None, cheap, 30).reason
    assert decide(LOW_RISK, GOOD_FIT, None, fair, 30).action == "bid"


def test_hourly_budget_compared_to_hourly_floor_and_missing_budget_is_not_penalised():
    assert budget_below_floor({"budget": {"type": "hourly", "max": 15}}, 30)
    assert budget_below_floor({"budget": {"type": "hourly", "max": 45}}, 30) is None
    assert budget_below_floor({"budget": {"min": 0, "max": 0}}, 30) is None          # unknown budget: not a floor violation
    assert budget_below_floor(None, 30) is None
