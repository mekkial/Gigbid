"""Explicit promotion rules (R7). Nothing enters long-term memory except through these functions.

STYLE  : an edit pattern (e.g. a phrase the user keeps deleting, always cutting the first sentence, always shortening)
         is promoted to a style rule when it recurs >= style_promote_min_count times across
         >= style_promote_min_jobs distinct jobs.
OUTCOME: per job category, win/reply counters are promoted to an outcome record only once n >= outcome_promote_min_n.
"""
from __future__ import annotations

import difflib
import re
import time

from agent.llm import load_config


def _words(t: str) -> list[str]:
    return re.findall(r"\S+", t)


def _sentences(t: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s]


def edit_features(original: str, edited: str) -> list[str]:
    feats = []
    o, e = _sentences(original), _sentences(edited)
    if o and e and o[0] not in e and len(e) < len(o):
        feats.append("cut_first_sentence")
    ow, ew = _words(original), _words(edited)
    if len(ew) < 0.85 * len(ow):
        feats.append("shorten")
    sm = difflib.SequenceMatcher(a=[w.lower().strip(".,;:!?") for w in ow], b=[w.lower().strip(".,;:!?") for w in ew])
    for tag, i1, i2, _, _ in sm.get_opcodes():
        if tag in ("delete", "replace") and 1 <= i2 - i1 <= 2:
            span = " ".join(w.lower().strip(".,;:!?") for w in ow[i1:i2])
            if len(span) >= 5 and not re.search(r"\d|evidence", span):
                feats.append(f"avoid:{span}")
    return sorted(set(feats))


def _rule_text(feat: str) -> str:
    if feat == "cut_first_sentence":
        return "Cut the generic first sentence; open directly with the client's problem."
    if feat == "shorten":
        return "Keep the cover letter concise (the user usually shortens drafts)."
    return f"Avoid the phrase '{feat.split(':', 1)[1]}'."


def record_edit(store, user: str, job_id: str, original: str, edited: str) -> list[dict]:
    """Count edit features; promote a feature to a style rule when the rule thresholds are met."""
    cfg = load_config()["memory"]
    promoted = []
    for f in edit_features(original, edited):
        item = store.get(("style_candidates", user), f)
        v = item.value if item else {"count": 0, "jobs": []}
        v["count"] += 1
        if job_id not in v["jobs"]:
            v["jobs"].append(job_id)
        store.put(("style_candidates", user), f, v)
        if v["count"] >= cfg["style_promote_min_count"] and len(v["jobs"]) >= cfg["style_promote_min_jobs"] \
                and not store.get(("style", user), f):
            rule = {"rule": _rule_text(f), "feature": f, "evidence_count": v["count"], "jobs": v["jobs"],
                    "promoted_at": time.time()}
            store.put(("style", user), f, rule)
            promoted.append(rule)
    return promoted


def style_rules(store, user: str) -> list[str]:
    return [i.value["rule"] for i in store.search(("style", user), limit=50)]


def record_outcome(store, user: str, category: str, outcome: str) -> dict | None:
    """outcome in {won, replied, ignored, lost}. Promote category stats once n >= outcome_promote_min_n."""
    cfg = load_config()["memory"]
    raw = store.get(("outcome_raw", user), category)
    v = raw.value if raw else {"n": 0, "won": 0, "replied": 0}
    v["n"] += 1
    v["won"] += outcome == "won"
    v["replied"] += outcome in ("won", "replied", "interview")
    store.put(("outcome_raw", user), category, v)
    if v["n"] >= cfg["outcome_promote_min_n"]:
        rec = {"category": category, "n": v["n"], "win_rate": v["won"] / v["n"], "reply_rate": v["replied"] / v["n"],
               "promoted_at": time.time()}
        store.put(("outcome", user), category, rec)
        return rec
    return None


def win_prob_hint(store, user: str, category: str) -> float | None:
    it = store.get(("outcome", user), category)
    return it.value["reply_rate"] * 0.5 if it else None
