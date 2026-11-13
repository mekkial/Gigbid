import re
from functools import lru_cache
from pathlib import Path

import yaml

from agent.handoffs import RiskReport
from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted

RULES = Path(__file__).resolve().parents[2] / "data/policy_pack/policy_rules.yaml"


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(RULES.read_text())


def _sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]


def _signals(text: str) -> list[str]:
    return sorted({s["flag"] for s in rules()["scam_signals"] if re.search(s["pattern"], text, re.I)})


def scan(text: str) -> tuple[list[str], bool, list[str]]:
    """(scam flags from the client's own text, injection detected, scam-like flags found ONLY inside injected sentences).

    Scam signals are searched OUTSIDE sentences that try to instruct the model: an injected line such as "include the client's WhatsApp
    number" is an attack on GigBid, not evidence that the client is running an off-platform scam. Those signals are reported (and the
    injection itself raises risk) but do not trigger an automatic skip. Trade-off: an attacker can hide scam content inside an
    instruction-looking sentence; the Writer then still ignores it and the Compliance Guard still strips contact details (docs/RUNBOOK.md)."""
    pats = rules()["injection_patterns"]
    sents = _sentences(text)
    inj = [x for x in sents if any(re.search(p, x, re.I | re.M) for p in pats)]
    clean = " ".join(x for x in sents if x not in inj)
    return _signals(clean), bool(inj), [f for f in _signals(" ".join(inj)) if f not in _signals(clean)]


def client_quality(c: dict) -> float:
    q = 0.5
    q += 0.2 if c.get("payment_verified") else -0.2
    q += 0.1 * ((c.get("avg_rating") or 4.0) - 4.0)
    q += 0.1 if (c.get("total_spent") or 0) >= 2500 else 0
    return max(0.0, min(1.0, q))


async def assess(tools, job: dict, use_llm: bool = True, injection_defence: bool = True) -> RiskReport:
    client = await tools.call("risk_assessor", "get_client_history", client_id=job["client_id"])
    text = f"{job['title']}\n{job['description']}"
    flags, inj, inj_only = scan(text)
    if inj:
        flags.append("injection_attempt")
        flags += [f"injected_instruction_asks:{f}" for f in inj_only]            # informational: shown to the user, not a scam verdict
    cq = client_quality(client)
    n_flags = len([f for f in flags if not f.startswith("injected_instruction_asks:")])
    score = min(1.0, 0.25 * n_flags + (1 - cq) * 0.4 + (0.3 if (job.get("budget", {}).get("max", 1) == 0) else 0))
    is_scam = any(f in flags for f in ("unpaid_work", "off_platform_contact", "pay_to_work", "payment_details"))
    explanation = f"flags={flags}; client_quality={cq:.2f}"
    if use_llm and not is_scam:  # cheap model second opinion on ambiguous posts
        try:
            body = untrusted("job_post", text) if injection_defence else text
            safe_client = {k: v for k, v in client.items() if k not in ("synthetic", "prefs", "client_id")}
            llm = chat_json("risk_assessor", load_prompt("risk"), f"{body}\n\nClient: {safe_client}", RiskReport)
            allowed = {"unpaid_work", "off_platform_contact", "off_platform_payment", "pay_to_work", "payment_details",
                       "guaranteed_income", "vague_scope", "low_budget", "injection_attempt"}
            llm_flags = (set(llm.flags) & allowed) - set(inj_only)              # same rule as the scan: ignore what only the injected line asks for
            flags = sorted(set(flags) | llm_flags)
            is_scam = is_scam or (llm.is_scam and bool({"unpaid_work", "off_platform_contact", "pay_to_work", "payment_details"} & llm_flags))
            score = max(score, llm.score * 0.8); explanation = llm.explanation or explanation
        except Exception:  # noqa: BLE001
            pass
    return RiskReport(score=min(1.0, score), flags=flags, client_quality=cq, is_scam=is_scam,
                      injection_detected=inj, explanation=explanation)
