"""What the 30 human labels say beyond judge agreement: acceptable rate by variant, and the copied-opening pattern.
Run after judge_calibration --score:  python -m evals.runners.label_analysis"""
import csv
import json
import re
import statistics as st
from pathlib import Path

from scipy.stats import fisher_exact

RES = Path(__file__).resolve().parents[1] / "results"


def words(s): return re.findall(r"[a-z0-9]+", s.lower())


def longest_shared_run(opening: str, job_text: str) -> int:
    """Length (words) of the longest word sequence of `opening` that also appears verbatim in the job text."""
    fw, jw, best = words(opening), " ".join(words(job_text)), 0
    for a in range(len(fw)):
        for b in range(a + best + 1, len(fw) + 1):
            if " ".join(fw[a:b]) in jw: best = b - a
            else: break
    return best


def first_sentence(p: str) -> str: return re.split(r"(?<=[.!?])\s", p.strip(), maxsplit=1)[0]


def main():
    rows = list(csv.DictReader(open(RES / "judge_calibration_sheet.csv", encoding="utf-8")))
    hid = json.load(open(RES / "judge_calibration_hidden.json"))
    ak = next(k for k in rows[0] if k.startswith("human_acc")); ok = next(k for k in rows[0] if k.startswith("human_over"))
    out = {"n": len(rows), "human_acceptable": sum(int(r[ak]) for r in rows), "judge_acceptable": sum(h["judge"]["acceptable"] for h in hid),
           "human_mean_overall": round(st.mean(int(r[ok]) for r in rows), 2), "judge_mean_overall": round(st.mean(h["judge"]["overall"] for h in hid), 2), "by_variant": {}}
    for v in ("v0_naive", "v3_rerank"):
        idx = [i for i, h in enumerate(hid) if h["variant"] == v]
        out["by_variant"][v] = {"n": len(idx), "human_acceptable": sum(int(rows[i][ak]) for i in idx), "judge_acceptable": sum(hid[i]["judge"]["acceptable"] for i in idx),
                                "human_mean_overall": round(st.mean(int(rows[i][ok]) for i in idx), 2), "judge_mean_overall": round(st.mean(hid[i]["judge"]["overall"] for i in idx), 2)}
    a, b = out["by_variant"]["v0_naive"], out["by_variant"]["v3_rerank"]
    out["fisher_p_acceptable_v0_vs_v3"] = round(fisher_exact([[a["human_acceptable"], a["n"] - a["human_acceptable"]], [b["human_acceptable"], b["n"] - b["human_acceptable"]]])[1], 3)
    runs = [longest_shared_run(first_sentence(r["proposal"]), r["job_title"] + " " + r["job_description"]) for r in rows]
    cp = [i for i, x in enumerate(runs) if x >= 6]; rest = [i for i in range(len(rows)) if i not in cp]
    ca, ra = sum(int(rows[i][ak]) for i in cp), sum(int(rows[i][ak]) for i in rest)
    out["copied_opening"] = {"threshold_words": 6, "n_copied": len(cp), "human_acceptable_when_copied": f"{ca}/{len(cp)}", "human_acceptable_otherwise": f"{ra}/{len(rest)}",
                             "fisher_p": round(fisher_exact([[ca, len(cp) - ca], [ra, len(rest) - ra]])[1], 3)}
    (RES / "label_analysis.json").write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
