"""Deterministic stand-ins for the LLM nodes. Used by tests, the Playwright e2e server and CI smoke runs so graph logic
can be exercised without network or API cost. NEVER used in production or in any reported quality number."""
from __future__ import annotations

from agent.handoffs import Claim, Critique, ProposalDraft
from agent.nodes import analyst, risk_assessor


def offline_impl(critic_script=None):
    from agent.graphs.bid_graph import Impl
    script = list(critic_script or [True])

    async def assess(tools, job, **kw):
        return await risk_assessor.assess(tools, job, use_llm=False)

    def write(job, spec, fit, price, evidence, style, feedback=None, revision=0):
        ids = [e["id"] for e in evidence][:2]
        first = ids[0] if ids else "none"
        txt = (f"Your {job['title'].lower()} is a good match for work I have done. I recently delivered {first} using "
               f"{', '.join(spec.required_skills[:3])} [evidence: {first}].\n\n"
               + " ".join(["I would start by confirming scope, then ship a first version quickly and iterate with you."] * 6)
               + "\n\nHappy to answer any questions about the approach.")
        return ProposalDraft(job_id=spec.job_id, cover_letter=txt, evidence_ids=ids, revision=revision)

    def review(job, draft, unsupported):
        ok = script.pop(0) if script else True
        return Critique(approved=ok, grounding=.9, personalisation=.8, issues=[] if ok else ["too generic"])

    return Impl(analyse=analyst.deterministic_spec, assess=assess, write=write,
                verify_claims=lambda text, ev: [Claim(text="I recently delivered it", verdict="supported", evidence_ids=[])], review=review)
