"""Fail the build if bid-or-skip F1 drops or unsupported claims / injection ASR rise past evals/thresholds.yaml."""
import json, pathlib, sys
import yaml

root = pathlib.Path(__file__).resolve().parent
th = yaml.safe_load((root / "thresholds.yaml").read_text())
res = json.loads((root / "results/smoke.json").read_text())
checks = [("bid_or_skip_f1", res["bid_or_skip"]["f1"], th["min_bid_or_skip_f1"], ">="), ("scam_recall", res["scam"]["recall"], th["min_scam_recall"], ">="),
          ("unsupported_rate_after_verification", res["unsupported_rate_after_verification"], th["max_unsupported_rate_after_verification"], "<=")]
bad = [c for c in checks if (c[1] < c[2] if c[3] == ">=" else c[1] > c[2])]
for n, v, t, op in checks:
    print(f"{'FAIL' if (n, v, t, op) in bad else 'ok  '} {n}: {v} (needs {op} {t})")
sys.exit(1 if bad else 0)
