"""Toolbox: the only way agent nodes reach portfolio/marketplace/workspace capabilities.

Backends are swappable: `LocalToolbox` (in-process, tests/evals) and `MCPToolbox` (agent/mcp_client.py,
real MCP servers). Nodes depend on this interface only (A6: each node gets an allowlist of tool names).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[1]
MARKET_STATS = ROOT / "data/processed/market_stats.json"

NODE_TOOL_ALLOWLIST = {  # enforced by Toolbox.call
    "scout": {"search_jobs", "get_job"},
    "risk_assessor": {"get_client_history", "get_job"},
    "fit_matcher": {"search_evidence", "list_skills"},
    "pricing": {"get_connects_balance", "get_market_stats"},
    "writer": {"search_evidence", "get_case_study"},
    "critic": {"search_evidence"},
    "client_liaison": {"list_messages", "free_slots", "search_evidence", "send_message", "create_tentative_hold"},
    "submit": {"create_proposal_draft", "submit_proposal"},
}


class ToolNotAllowed(Exception):
    pass


class Toolbox(Protocol):
    async def call(self, node: str, tool: str, **args: Any) -> Any: ...


def market_stats(persona: str) -> dict:
    s = json.loads(MARKET_STATS.read_text()) if MARKET_STATS.exists() else {}
    return s.get(persona, s.get("_overall_2024_50k", {}))


class LocalToolbox:
    """In-process backend over the retriever + marketplace port (same tool names/semantics as the MCP servers)."""

    def __init__(self, persona: str, marketplace, index=None, retrieve=None, workspace=None):
        from rag.index.store import Index
        from rag.ingest.loaders import load_persona
        from rag.retriever import get_retriever

        self.persona, self.mp, self.workspace = persona, marketplace, workspace
        self.index = index or Index(load_persona(persona))
        self.retrieve = retrieve or get_retriever()
        self.profile = json.loads((ROOT / "data/personas" / persona / "profile.json").read_text())

    async def call(self, node: str, tool: str, **args: Any) -> Any:
        if tool not in NODE_TOOL_ALLOWLIST.get(node, set()):
            raise ToolNotAllowed(f"{node} may not call {tool}")
        if tool == "search_evidence":
            return self.search_evidence(args["requirement"], args.get("k", 3))
        if tool == "list_skills":
            return self.profile["skills"]
        if tool == "get_case_study":
            return [c for c in self.index.chunks if c["project"] == args["id"]]
        if tool == "get_market_stats":
            return market_stats(self.persona)
        if tool == "create_tentative_hold":
            return {"hold_id": "local-hold", "slot": args["slot"], "title": args["title"], "status": "tentative"}
        if tool == "free_slots":
            return await self.workspace.free_slots() if self.workspace else ["Tue 10:00", "Wed 15:00", "Thu 11:00"]
        return await getattr(self.mp, tool)(**args)

    def search_evidence(self, requirement: str, k: int = 3) -> list[dict]:
        """Evidence items collapsed to projects: id, type, source, date, outcome, text."""
        seen, out = set(), []
        for c in self.retrieve(requirement, self.index, k=30):
            pid = c["project"]
            if pid in seen or pid == "cv":
                continue
            seen.add(pid)
            texts = [x["text"] for x in self.index.chunks if x["project"] == pid and x["type"] in ("case_study", "readme")]
            out.append({"id": pid, "type": c["type"], "source": f"{c['type']}:{pid}", "date": c["date"],
                        "outcome": c.get("outcome"), "skills": c["skills"], "text": " ".join(texts)[:900]})
            if len(out) >= k:
                break
        return out
