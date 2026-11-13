from agent.handoffs import FitReport, JobSpec, PriceQuote, RiskReport


async def quote(tools, spec: JobSpec, fit: FitReport, risk: RiskReport, floor_hourly: float, connects_cost: int,
                win_prob_hint: float | None = None) -> PriceQuote:
    stats = await tools.call("pricing", "get_market_stats")
    bal = await tools.call("pricing", "get_connects_balance")
    bmax, bmin = spec.budget_max or 0, spec.budget_min or 0
    kind = "hourly" if spec.budget_type == "hourly" else "fixed"
    p50 = (stats.get(kind) or {}).get("p50")
    if kind == "hourly":
        target = max(floor_hourly, min(bmax or 1e9, (p50 or floor_hourly) * (1 + 0.25 * fit.score)))
        floor = floor_hourly
    else:
        floor = floor_hourly * 8            # floor: at least ~8 hours of work
        target = max(floor, (bmin + bmax) / 2 if bmax else (p50 or floor))
        if bmax and target > bmax:
            target = bmax
    # Connects worth it? expected value of winning vs cost of Connects (~$0.15 each)
    p_win = win_prob_hint if win_prob_hint is not None else max(0.03, 0.25 * fit.score * (1 - risk.score))
    ev = p_win * target
    worth = ev > connects_cost * 0.15 * 10 and bal["balance"] >= connects_cost
    return PriceQuote(amount=round(max(target, 1), 2), budget_type=kind, floor=floor, market_p50=p50,
                      connects_cost=connects_cost, connects_worth_it=worth,
                      rationale=f"{kind} target {target:.0f} vs floor {floor:.0f}, market p50 {p50}; win prob {p_win:.2f}, "
                                f"EV {ev:.0f}; connects {connects_cost} (balance {bal['balance']})")
