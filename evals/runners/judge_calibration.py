"""LLM-judge calibration and the blind pairwise human panel (B4). HUMAN LABELS ARE NEVER GENERATED HERE: this script only prepares sheets
for a person to fill in and computes agreement (Cohen's kappa) once they are filled.

  python -m evals.runners.judge_calibration prepare          -> 30-item sheet  (evals/results/judge_calibration_sheet.csv, judge scores withheld)
  python -m evals.runners.judge_calibration score            -> kappa judge vs YOU (evals/results/judge_calibration.json) + disagreements to discuss
  python -m evals.runners.judge_calibration panel-prepare    -> anonymised A/B pairs for classmates (pairwise_panel.csv + secret key)
  python -m evals.runners.judge_calibration panel-score      -> win rate + exact binomial p-value (pairwise_panel_result.json)
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "evals/results"
SEED = 4016


def cohen_kappa(a: list, b: list) -> float:
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def weighted_kappa(a: list[int], b: list[int], cats=(1, 2, 3, 4, 5)) -> float:
    """Quadratic-weighted kappa for the ordinal 1-5 overall score."""
    k = len(cats); n = len(a)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - 1][y - 1] += 1
    ra = [sum(r) for r in obs]; cb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2)
            num += w * obs[i][j] / n; den += w * ra[i] * cb[j] / (n * n)
    return 1.0 if den == 0 else 1 - num / den


def binom_two_sided(k: int, n: int) -> float:
    p = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    return round(min(1.0, sum(x for x in p if x <= p[k] + 1e-12)), 4)


def _load_proposals():
    rows = []
    for f in sorted(RES.glob("proposals_*.jsonl")):
        variant = f.stem.removeprefix("proposals_")
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if r.get("text"):
                rows.append({"variant": variant, **r})
    return rows


def prepare():
    rows = _load_proposals(); rng = random.Random(SEED); rng.shuffle(rows)
    pick = rows[:30]
    if len(pick) < 30:
        print(f"only {len(pick)} proposals available; run proposal_eval first"); return
    jobs = {}
    for p in ("ai_ml", "fullstack", "data_analyst"):
        for line in (ROOT / "evals/datasets" / f"dev_{p}.jsonl").read_text().splitlines():
            j = json.loads(line); jobs[j["job_id"]] = j
    with open(RES / "judge_calibration_sheet.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["item", "job_title", "job_description", "proposal", "human_acceptable (1=yes,0=no)", "human_overall (1-5)"])
        for i, r in enumerate(pick):
            j = jobs[r["job_id"]]; w.writerow([i, j["title"], j["description"], r["text"], "", ""])
    (RES / "judge_calibration_key.json").write_text(json.dumps([{"item": i, "variant": r["variant"], "job_id": r["job_id"], "judge": r["judge"]} for i, r in enumerate(pick)], indent=1))
    print("wrote judge_calibration_sheet.csv: fill the last two columns YOURSELF (do not look at judge_calibration_key.json), then run `score`")


def score():
    key = json.loads((RES / "judge_calibration_key.json").read_text())
    rows = list(csv.DictReader(open(RES / "judge_calibration_sheet.csv")))
    h_acc, h_ov, j_acc, j_ov, items = [], [], [], [], []
    for r, k in zip(rows, key):
        if not r["human_acceptable (1=yes,0=no)"].strip():
            continue
        h_acc.append(int(r["human_acceptable (1=yes,0=no)"])); h_ov.append(int(r["human_overall (1-5)"]))
        j_acc.append(int(k["judge"]["acceptable"])); j_ov.append(int(k["judge"]["overall"])); items.append((k, r))
    if len(h_acc) < 30:
        print(f"{len(h_acc)}/30 labelled; label all 30 first"); return
    dis = [{"item": k["item"], "human_overall": h, "judge_overall": j, "proposal": r["proposal"][:300]} for (k, r), h, j in zip(items, h_ov, j_ov) if abs(h - j) >= 2]
    out = {"n": len(h_acc), "kappa_acceptable": round(cohen_kappa(h_acc, j_acc), 3), "weighted_kappa_overall": round(weighted_kappa(h_ov, j_ov), 3),
           "agreement_acceptable": round(sum(a == b for a, b in zip(h_acc, j_acc)) / len(h_acc), 3), "disagreements_2plus_points": dis[:6],
           "reading": "kappa < 0.4 poor, 0.4-0.6 moderate, 0.6-0.8 substantial, > 0.8 near-perfect. Report judge scores only next to this number."}
    (RES / "judge_calibration.json").write_text(json.dumps(out, indent=2)); print(json.dumps({k: v for k, v in out.items() if k != "disagreements_2plus_points"}))


def panel_prepare(n_pairs: int = 20):
    by = {}
    for r in _load_proposals():
        by.setdefault(r["job_id"], {})[r["variant"]] = r["text"]
    pairs = [(j, v) for j, v in by.items() if len(v) >= 2]
    rng = random.Random(SEED); rng.shuffle(pairs); key = []
    with open(RES / "pairwise_panel.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pair", "proposal_A", "proposal_B", "preferred (A/B)"])
        for i, (job, v) in enumerate(pairs[:n_pairs]):
            names = sorted(v)[:2]; rng.shuffle(names)
            w.writerow([i, v[names[0]], v[names[1]], ""]); key.append({"pair": i, "job_id": job, "A": names[0], "B": names[1]})
    (RES / "pairwise_panel_key.json").write_text(json.dumps(key, indent=1)); print(f"wrote pairwise_panel.csv ({len(key)} pairs, anonymised and randomised)")


def panel_score():
    key = json.loads((RES / "pairwise_panel_key.json").read_text()); wins = Counter(); n = 0
    for fname in sorted(RES.glob("pairwise_panel*.csv")):          # one file per rater: pairwise_panel_<name>.csv
        for r, k in zip(csv.DictReader(open(fname)), key):
            c = r["preferred (A/B)"].strip().upper()
            if c in ("A", "B"):
                wins[k[c]] += 1; n += 1
    if not n:
        print("no ratings yet"); return
    top, k = wins.most_common(1)[0]
    out = {"n_ratings": n, "wins": dict(wins), "p_value_two_sided_binomial": binom_two_sided(k, n)}
    (RES / "pairwise_panel_result.json").write_text(json.dumps(out, indent=2)); print(out)


if __name__ == "__main__":
    {"prepare": prepare, "score": score, "panel-prepare": panel_prepare, "panel-score": panel_score}[sys.argv[1] if len(sys.argv) > 1 else "prepare"]()
