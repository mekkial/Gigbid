"""Judge calibration (B4): the LLM judge is only trusted next to its agreement with HUMAN labels.
  python -m evals.runners.judge_calibration --make-sheet     -> evals/results/judge_calibration_sheet.csv  (30 anonymised proposals; fill the two human_* columns)
  python -m evals.runners.judge_calibration --score          -> evals/results/judge_calibration.json      (Cohen's kappa; quadratic-weighted kappa on 1-5)
The sheet deliberately omits the judge's scores so labelling is blind; they are kept in judge_calibration_hidden.json."""
from __future__ import annotations

import argparse
import csv
import glob
import json
import random
from collections import Counter

from evals.runners.rag_eval import ROOT, load_jobs

RES = ROOT / "evals/results"


def cohen_kappa(a: list, b: list) -> float:
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def quad_kappa(a: list[int], b: list[int], lo=1, hi=5) -> float:
    k = hi - lo + 1; n = len(a)
    O = [[0] * k for _ in range(k)]
    for x, y in zip(a, b): O[x - lo][y - lo] += 1
    ha, hb = [sum(r) for r in O], [sum(O[i][j] for i in range(k)) for j in range(k)]
    num = sum(((i - j) ** 2) * O[i][j] for i in range(k) for j in range(k)) / n
    den = sum(((i - j) ** 2) * ha[i] * hb[j] for i in range(k) for j in range(k)) / (n * n)
    return 1.0 if den == 0 else 1 - num / den


weighted_kappa = quad_kappa      # public name used by the tests and the report


def binom_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial (sign) test: used for the blind pairwise human panel (is variant A preferred more often than chance?)."""
    from math import comb
    pm = [comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    return min(1.0, sum(x for x in pm if x <= pm[k] + 1e-12))


def make_sheet(n=30, seed=4016):
    rows = []
    for f in glob.glob(str(RES / "proposals_*.jsonl")):
        rows += [json.loads(l) | {"variant": f.split("proposals_")[1][:-6]} for l in open(f)]
    rows = [r for r in rows if r.get("text") and r.get("judge")]
    if len(rows) < n:
        raise SystemExit(f"need >= {n} judged proposals; run proposal_eval first (have {len(rows)})")
    random.Random(seed).shuffle(rows); rows = rows[:n]
    jobs = {j["job_id"]: j for p in ("ai_ml", "fullstack", "data_analyst") for j in load_jobs(p)}
    with open(RES / "judge_calibration_sheet.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["item", "job_title", "job_description", "proposal", "human_acceptable (1/0)", "human_overall (1-5)"])
        for i, r in enumerate(rows):
            j = jobs[r["job_id"]]; w.writerow([i, j["title"], j["description"][:400], r["text"], "", ""])
    (RES / "judge_calibration_hidden.json").write_text(json.dumps([{"item": i, "variant": r["variant"], "job_id": r["job_id"], "judge": r["judge"]} for i, r in enumerate(rows)], indent=1))
    print("wrote judge_calibration_sheet.csv: label the last two columns yourself (do NOT look at the judge), then run --score")


def score():
    hidden = json.loads((RES / "judge_calibration_hidden.json").read_text())
    rows = list(csv.DictReader(open(RES / "judge_calibration_sheet.csv")))
    h_acc, h_ov, j_acc, j_ov, items = [], [], [], [], []
    for r, h in zip(rows, hidden):
        if not r["human_acceptable (1/0)"].strip() or not r["human_overall (1-5)"].strip():
            continue
        h_acc.append(int(r["human_acceptable (1/0)"])); h_ov.append(int(r["human_overall (1-5)"]))
        j_acc.append(int(h["judge"]["acceptable"])); j_ov.append(int(h["judge"]["overall"])); items.append(h["item"])
    if len(items) < 30:
        raise SystemExit(f"only {len(items)} labelled items; the brief requires 30")
    out = {"n_labelled": len(items), "kappa_acceptable": round(cohen_kappa(h_acc, j_acc), 3), "weighted_kappa_overall_1to5": round(quad_kappa(h_ov, j_ov), 3),
           "raw_agreement_acceptable": round(sum(x == y for x, y in zip(h_acc, j_acc)) / len(items), 3),
           "disagreements": [{"item": i, "human": ha, "judge": ja} for i, ha, ja in zip(items, h_acc, j_acc) if ha != ja][:10],
           "interpretation": "kappa < 0.4 poor, 0.4-0.6 moderate, 0.6-0.8 substantial: report judge scores only alongside this number"}
    (RES / "judge_calibration.json").write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--make-sheet", action="store_true"); ap.add_argument("--score", action="store_true"); a = ap.parse_args()
    make_sheet() if a.make_sheet else score() if a.score else ap.print_help()
