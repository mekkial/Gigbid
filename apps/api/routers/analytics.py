from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api import db
from apps.api.auth.security import current_user
from apps.api.schemas.models import AnalyticsOut

router = APIRouter(tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(user: dict = Depends(current_user)):
    uid = user["id"]
    tot = (await db.fetch("SELECT count(*) AS runs, count(*) FILTER (WHERE status='submitted') AS submitted, count(*) FILTER (WHERE decision='skip') AS skipped, "
                          "count(*) FILTER (WHERE status='awaiting_approval') AS pending FROM runs WHERE user_id=%s AND kind='bid'", uid))[0]
    cat = await db.fetch("SELECT category, count(*) FILTER (WHERE status='submitted') AS sent, count(*) FILTER (WHERE outcome IN ('reply','interview','hire')) AS replies, "
                         "count(*) FILTER (WHERE outcome='hire') AS hires FROM runs WHERE user_id=%s AND kind='bid' GROUP BY category", uid)
    for c in cat:
        c["reply_rate"] = c["replies"] / c["sent"] if c["sent"] else None
        c["hire_rate"] = c["hires"] / c["sent"] if c["sent"] else None
    conn = (await db.fetch("SELECT COALESCE(sum(connects) FILTER (WHERE status='submitted'),0) AS spent, "
                           "COALESCE(sum(connects) FILTER (WHERE outcome='hire'),0) AS spent_on_hires FROM runs WHERE user_id=%s", uid))[0]
    cl = (await db.fetch("SELECT COALESCE(avg(cost_usd) FILTER (WHERE price IS NOT NULL),0) AS avg_cost_per_proposal, COALESCE(avg(latency_s) FILTER (WHERE price IS NOT NULL),0) AS avg_latency_s, "
                         "COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_s) FILTER (WHERE price IS NOT NULL),0) AS p95_latency_s, "
                         "COALESCE(avg(cost_usd),0) AS avg_cost_per_job, COALESCE(sum(tokens),0) AS tokens FROM runs WHERE user_id=%s AND kind='bid'", uid))[0]
    rej = await db.fetch("SELECT summary->'approval'->>'reason' AS reason, count(*) AS n FROM runs WHERE user_id=%s AND status='rejected' GROUP BY 1 ORDER BY n DESC LIMIT 5", uid)
    return AnalyticsOut(totals=tot, by_category=cat, connects=conn, cost_latency=cl, rejection_reasons=rej)
