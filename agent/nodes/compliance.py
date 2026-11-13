import re

from agent.handoffs import ComplianceVerdict
from agent.nodes.risk_assessor import rules


def check(text: str) -> ComplianceVerdict:
    """Enforce the policy pack: strip contact details, guarantees and banned phrases; block if it cannot be cleaned."""
    r, violations, cleaned = rules(), [], text
    for kind, pats in r["forbidden_patterns"].items():
        for p in pats:
            if re.search(p, cleaned, re.I):
                violations.append(kind)
                cleaned = re.sub(p, "", cleaned, flags=re.I)
    for ph in r["banned_phrases"]:
        if re.search(re.escape(ph), cleaned, re.I):
            violations.append(f"banned_phrase:{ph}")
            cleaned = re.sub(re.escape(ph), "", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    lim = r["limits"]
    if len(cleaned) < lim["proposal_min_chars"] or len(cleaned) > lim["proposal_max_chars"]:
        violations.append("length_out_of_bounds")
    blocking = [v for v in violations if v == "length_out_of_bounds"]
    return ComplianceVerdict(allowed=not blocking, violations=sorted(set(violations)), cleaned_text=cleaned)


def strip_citations(text: str) -> str:
    """Internal [evidence: id] markers are for the UI hover; never sent to the marketplace."""
    return re.sub(r"\s*\[evidence:[^\]]*\]", "", text)
