import re

from agent.handoffs import ComplianceVerdict
from agent.nodes.risk_assessor import rules


def _is_date_or_time(s: str) -> bool:
    """The phone-number pattern also matches ISO dates and times such as interview slots ('2026-11-16 10:00'); those are not contact details."""
    return bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", s)) and not re.search(r"\d{9,}", re.sub(r"[\s().-]", "", re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", s)))


def check(text: str) -> ComplianceVerdict:
    """Enforce the policy pack: strip contact details, guarantees and banned phrases; block if it cannot be cleaned."""
    r, violations, cleaned = rules(), [], text
    for kind, pats in r["forbidden_patterns"].items():
        for p in pats:
            hits = [m for m in re.finditer(p, cleaned, re.I) if not _is_date_or_time(m.group())]
            if hits:
                violations.append(kind)
                for m in reversed(hits):
                    cleaned = cleaned[:m.start()] + cleaned[m.end():]
    for ph in r["banned_phrases"]:
        if re.search(re.escape(ph), cleaned, re.I):
            violations.append(f"banned_phrase:{ph}")
            cleaned = re.sub(re.escape(ph), "", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    for phrase in r.get("required_phrases", []):               # platform-mandated text is appended, never duplicated
        if phrase.lower() not in cleaned.lower():
            cleaned = f"{cleaned}\n\n{phrase}"
    lim = r["limits"]
    if len(cleaned) < lim["proposal_min_chars"] or len(cleaned) > lim["proposal_max_chars"]:
        violations.append("length_out_of_bounds")
    blocking = [v for v in violations if v == "length_out_of_bounds"]
    return ComplianceVerdict(allowed=not blocking, violations=sorted(set(violations)), cleaned_text=cleaned)


def strip_citations(text: str) -> str:
    """Internal [evidence: id] markers are for the UI hover; never sent to the marketplace."""
    return re.sub(r"\s*\[evidence:[^\]]*\]", "", text)
