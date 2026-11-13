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


def scan(text: str) -> tuple[list[str], bool]:
    r, flags = rules(), []
    for s in r["scam_signals"]:
        if re.search(s["pattern"], text, re.I):
            flags.append(s["flag"])
    inj = any(re.search(p, text, re.I | re.M) for p in r["injection_patterns"])
    return sorted(set(flags)), inj


def client_quality(c: dict) -> float:
    q = 0.5
    q += 0.2 if c.get("payment_verified") else -0.2
    q += 0.1 * ((c.get("avg_rating") or 4.0) - 4.0)
    q += 0.1 if (c.get("total_spent") or 0) >= 2500 else 0
    return max(0.0, min(1.0, q))


async def assess(tools, job: dict, use_llm: bool = True, injection_defence: bool = True) -> RiskReport:
    client = await tools.call("risk_assessor", "get_client_history", client_id=job["client_id"])
    text = f"{job['title']}\n{job['description']}"
    flags, inj = scan(text)
    if inj:
        flags.append("injection_attempt")
    cq = client_quality(client)
    score = min(1.0, 0.25 * len(flags) + (1 - cq) * 0.4 + (0.3 if (job.get("budget", {}).get("max", 1) == 0) else 0))
    is_scam = any(f in flags for f in ("unpaid_work", "off_platform_contact", "pay_to_work", "payment_details"))
    explanation = f"flags={flags}; client_quality={cq:.2f}"
    if use_llm and not is_scam:  # cheap model second opinion on ambiguous posts
        try:
            body = untrusted("job_post", text) if injection_defence else text
            safe_client = {k: v for k, v in client.items() if k not in ("synthetic", "prefs", "client_id")}
            llm = chat_json("risk_assessor", load_prompt("risk"), f"{body}\n\nClient: {safe_client}", RiskReport)
            allowed = {"unpaid_work", "off_platform_contact", "off_platform_payment", "pay_to_work", "payment_details",
                       "guaranteed_income", "vague_scope", "low_budget", "injection_attempt"}
            flags = sorted(set(flags) | (set(llm.flags) & allowed))
            is_scam = is_scam or (llm.is_scam and bool({"unpaid_work", "off_platform_contact", "pay_to_work", "payment_details"} & set(llm.flags)))
            score = max(score, llm.score * 0.8); explanation = llm.explanation or explanation
        except Exception:  # noqa: BLE001
            pass
    return RiskReport(score=min(1.0, score), flags=flags, client_quality=cq, is_scam=is_scam,
                      injection_detected=inj, explanation=explanation)
