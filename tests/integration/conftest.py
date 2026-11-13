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
g.RULES["connects"]["starting_balance"] = 10_000_000


def dev_jobs(persona="ai_ml"):
    return [json.loads(l) for l in open(f"evals/datasets/dev_{persona}.jsonl")]


@pytest.fixture(scope="session")
def toolbox():
    mp = GigSimAdapter(user="itest", client=httpx.AsyncClient(transport=httpx.ASGITransport(app=g.app), base_url="http://t"), backoff=0.01)
    return LocalToolbox("ai_ml", mp)


from agent.offline_impl import offline_impl  # noqa: E402,F401


@pytest.fixture
def make_graph(toolbox):
    def _make(critic_script=None, store=None, cp=None):
        store = store or InMemoryStore()
        cp = cp or MemorySaver()
        return build_bid_graph(toolbox, store, cp, offline_impl(critic_script)), store, cp
    return _make
