import asyncio

from agent.handoffs import FitReport, JobSpec, RequirementMatch


def _covers(req: str, item: dict) -> bool:
    r = req.lower()
    return any(r == s.lower() or r in s.lower() or s.lower() in r for s in item["skills"]) or r in item["text"].lower()


async def match(tools, spec: JobSpec, concurrent: bool = True) -> tuple[FitReport, list[dict]]:
    """Map every requirement to portfolio evidence (read-only Portfolio tools)."""
    matches, evidence, seen = [], [], set()
    # one search per requirement, issued concurrently (optimisation: ~sequential latency / #requirements; see evals/results/optimisation.json)
    results = await asyncio.gather(*[tools.call("fit_matcher", "search_evidence", requirement=r, k=3) for r in spec.required_skills]) if concurrent \
        else [await tools.call("fit_matcher", "search_evidence", requirement=r, k=3) for r in spec.required_skills]
    for req, items in zip(spec.required_skills, results):
        good = [i for i in items if _covers(req, i)]
        matches.append(RequirementMatch(requirement=req, evidence_ids=[i["id"] for i in good], supported=bool(good)))
        for i in good:
            if i["id"] not in seen:
                seen.add(i["id"]); evidence.append(i)
    n = max(1, len(matches))
    score = sum(m.supported for m in matches) / n
    sup = [m.requirement for m in matches if m.supported]; miss = [m.requirement for m in matches if not m.supported]
    return FitReport(score=score, matches=matches, matched_skills=sup, missing_skills=miss,
                     reasons=f"{len(sup)}/{n} requirements backed by portfolio evidence"), evidence
