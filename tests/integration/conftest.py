import json
import functools

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent.graphs.bid_graph import Impl, build_bid_graph
from agent.handoffs import Claim, Critique, ProposalDraft
from agent.nodes import risk_assessor
from agent.tools import LocalToolbox
from gigsim import app as g
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

g.RULES["error_rate_5xx"] = 0.0
g.RULES["rate_limit_per_minute"] = 100000


def dev_jobs(persona="ai_ml"):
    return [json.loads(l) for l in open(f"evals/datasets/dev_{persona}.jsonl")]


@pytest.fixture(scope="session")
def toolbox():
    mp = GigSimAdapter(user="itest", client=httpx.AsyncClient(transport=httpx.ASGITransport(app=g.app), base_url="http://t"), backoff=0.01)
    return LocalToolbox("ai_ml", mp)


def offline_impl(critic_script=None):
    """Deterministic stand-ins for the LLM nodes so graph logic is tested without network."""
    from agent.nodes import analyst
    script = list(critic_script or [True])

    async def assess(tools, job, **kw):
        return await risk_assessor.assess(tools, job, use_llm=False)

    def write(job, spec, fit, price, evidence, style, feedback=None, revision=0):
        ids = [e["id"] for e in evidence][:2]
        txt = f"I built {', '.join(ids)} recently. " + "Details attached. " * 20 + f"[evidence: {ids[0] if ids else 'none'}] rev{revision}"
        return ProposalDraft(job_id=spec.job_id, cover_letter=txt, evidence_ids=ids, revision=revision)

    def review(job, draft, unsupported):
        ok = script.pop(0) if script else True
        return Critique(approved=ok, grounding=.9, personalisation=.8, issues=[] if ok else ["too generic"])

    return Impl(analyse=analyst.deterministic_spec, assess=assess, write=write,
                verify_claims=lambda text, ev: [Claim(text="I built it", verdict="supported", evidence_ids=[])],
                review=review)


@pytest.fixture
def make_graph(toolbox):
    def _make(critic_script=None, store=None, cp=None):
        store = store or InMemoryStore()
        cp = cp or MemorySaver()
        return build_bid_graph(toolbox, store, cp, offline_impl(critic_script)), store, cp
    return _make
