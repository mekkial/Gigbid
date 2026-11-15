"""Clean REAL Kaggle Upwork data into GigBid's job schema (synthetic=false) + market statistics.

Sources (see docs/DATA_CARD.md):
  * ahmedmyalo/upwork-freelance-jobs-60k  -> jobs, skills (Category_1..9), Connects, client spend/rating
  * asaniczka/upwork-job-postings-dataset-2024-50k -> hourly/fixed budgets for pricing statistics
Run: python -m data.build.prepare_jobs
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW60 = ROOT / "data/raw/upwork_60k/Final_Upwork_Dataset.csv"
RAW50 = ROOT / "data/raw/upwork_50k/upwork-jobs.csv"
OUT = ROOT / "data/processed"
SEED = 4016

DOMAINS = {  # keyword -> persona bucket (used only to route jobs / stats, not as gold labels)
    "ai_ml": ["machine learning", "ai ", "nlp", "deep learning", "data science", "llm", "chatbot", "python", "tensorflow", "pytorch"],
    "fullstack": ["web development", "react", "node", "javascript", "full stack", "wordpress", "django", "next.js", "api", "website"],
    "data_analyst": ["data analysis", "power bi", "tableau", "sql", "excel", "data visualization", "dashboard", "etl", "analytics"],
}
_money = re.compile(r"[\d,]+(?:\.\d+)?")


def money(v) -> float | None:
    if pd.isna(v):
        return None
    m = _money.search(str(v))
    return float(m.group().replace(",", "")) if m else None


def bucket(text: str) -> str | None:
    t = f" {text.lower()} "
    scores = {k: sum(w in t for w in ws) for k, ws in DOMAINS.items()}
    k = max(scores, key=scores.get)
    return k if scores[k] > 0 else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    df = pd.read_csv(RAW60, low_memory=False)
    cat_cols = [f"Category_{i}" for i in range(1, 10)]
    df["skills"] = df[cat_cols].apply(lambda r: [str(x) for x in r if isinstance(x, str)], axis=1)
    df = df.dropna(subset=["Job Title", "Description"])
    df = df[df["Description"].str.len() > 80].drop_duplicates(subset=["Job Title", "Description"])
    jobs, clients = [], []
    for i, (_, r) in enumerate(df.iterrows()):
        text = f"{r['Job Title']} {' '.join(r['skills'])} {str(r['Description'])[:400]}"
        b = bucket(text)
        if b is None:
            continue
        fixed = str(r.get("Payment_type", "")).lower().startswith("fixed")
        cost = money(r.get("Job_Cost"))
        lo, hi = money(r.get("Start_rate")), money(r.get("End_rate"))
        budget = ({"min": cost or 0, "max": cost or 0, "currency": "USD", "type": "fixed"} if fixed
                  else {"min": lo or 0, "max": hi or lo or 0, "currency": "USD", "type": "hourly"})
        cid = f"real-client-{i:05d}"
        spent = money(r.get("Spent($)")) or 0
        rating = None if pd.isna(r.get("Rating")) else float(r["Rating"])
        clients.append({"client_id": cid, "industry": "unknown", "total_spent": spent, "hire_rate": None,
                        "avg_rating": rating, "payment_verified": "unverified" not in str(r.get("Payment_Situation", "")).lower(),
                        "country": r.get("Client_Country") if isinstance(r.get("Client_Country"), str) else None,
                        # hidden prefs are SYNTHETIC even though the client row is real
                        "prefs": {"must_have_skills": [], "budget_ceiling": max(300, (budget["max"] or 500) * 1.3),
                                  "dislikes_generic": rng.random() < 0.7}, "synthetic": False})
        cc = money(r.get("Connects_Num"))
        jobs.append({"job_id": f"real-{i:05d}", "client_id": cid, "persona_hint": b, "synthetic": False,
                     "title": str(r["Job Title"]).strip(), "description": str(r["Description"]).strip()[:3000],
                     "required_skills": r["skills"][:8], "budget": budget, "connects_cost": int(cc) if cc else 8,
                     "screening_questions": [], "posted_days_ago": rng.randint(0, 30), "source": "kaggle:upwork-freelance-jobs-60k"})
    rng.shuffle(jobs)
    jobs = jobs[:3000]
    keep = {j["client_id"] for j in jobs}
    clients = [c for c in clients if c["client_id"] in keep]
    (OUT / "real_jobs.jsonl").write_text("\n".join(json.dumps(j) for j in jobs))
    (OUT / "real_clients.json").write_text(json.dumps(clients))

    # ---- market statistics for the Pricing Strategist (fixed-price USD, hourly USD) ----
    stats: dict = {}
    for b in DOMAINS:
        sub = [j for j in jobs if j["persona_hint"] == b]
        fx = pd.Series([j["budget"]["max"] for j in sub if j["budget"]["type"] == "fixed" and j["budget"]["max"] > 0])
        hr = pd.Series([j["budget"]["max"] for j in sub if j["budget"]["type"] == "hourly" and j["budget"]["max"] > 0])
        q = lambda s: {"n": int(len(s)), "p25": float(s.quantile(.25)), "p50": float(s.quantile(.5)), "p75": float(s.quantile(.75))} if len(s) else {"n": 0}
        stats[b] = {"fixed": q(fx), "hourly": q(hr)}
    d50 = pd.read_csv(RAW50, low_memory=False)
    h = d50[(d50["is_hourly"] == True) & d50["hourly_high"].notna()]["hourly_high"]  # noqa: E712
    f = d50[(d50["is_hourly"] == False) & d50["budget"].notna()]["budget"]  # noqa: E712
    stats["_overall_2024_50k"] = {"hourly_high": {"n": int(len(h)), "p50": float(h.median())},
                                  "fixed": {"n": int(len(f)), "p50": float(f.median())}}
    (OUT / "market_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"real jobs={len(jobs)} clients={len(clients)}")
    print(json.dumps(stats, indent=1)[:900])


if __name__ == "__main__":
    main()
