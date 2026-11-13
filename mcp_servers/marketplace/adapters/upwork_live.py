"""Live Upwork adapter behind the SAME MarketplacePort as GigSim (R1/A4).

Talks to Upwork's official MCP server (Streamable HTTP, OAuth 2.1) through MultiServerMCPClient. Hard rules:
  * official MCP server only: no scraping, no browser automation, no session cookies
  * every WRITE is a DRAFT: `submit_proposal` never submits; the user confirms on Upwork as the platform requires
  * reads are rate-limited and the scheduler enforces `marketplace.live.min_poll_interval_min`
STATUS: implemented against the MCP spec and tested with a fake Upwork-style MCP server (tests/unit/test_upwork_live.py).
It has NOT been exercised against the real Upwork server (needs an Upwork account); see docs/RUNBOOK.md.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.llm import load_config
from agent.marketplace_port import MarketplaceUnavailable

KEYWORDS = {                      # all words must appear in the tool name (checked in order of specificity)
    "search_jobs": [["search", "job"], ["find", "job"], ["list", "job"]],
    "get_job": [["get", "job"], ["job", "detail"], ["job", "get"]],
    "get_client_history": [["client"], ["buyer"]],
    "get_connects_balance": [["connect"]],
    "list_messages": [["list", "message"], ["get", "message"], ["room", "message"], ["conversation"]],
    "create_proposal_draft": [["proposal", "draft"], ["create", "proposal"], ["draft", "proposal"]],
    "send_message": [["message", "draft"], ["send", "message"], ["create", "message"]],
}


class UpworkLiveAdapter:
    def __init__(self, access_token: str | None = None, user: str = "me", token_provider=None, connection: dict | None = None,
                 min_interval_s: float = 2.0, timeout: float = 30.0):
        cfg = load_config()["marketplace"]["live"]
        self.cfg, self.user, self.timeout = cfg, user, timeout
        self.token_provider = token_provider                    # async () -> access token (reads the encrypted vault)
        self._static = access_token
        self._conn = connection                                 # tests inject an in-memory/fake connection
        self._tools: dict[str, str] | None = None
        self._available: list[str] = []
        self._last = 0.0
        self._min_interval = min_interval_s                     # never hammer the platform
        self._lock = asyncio.Lock()

    async def _client(self) -> MultiServerMCPClient:
        if self._conn is not None:
            return MultiServerMCPClient({"upwork": self._conn})
        token = self._static or (await self.token_provider() if self.token_provider else None)
        if not token:
            raise MarketplaceUnavailable("Upwork is not connected: complete the OAuth flow in Settings first")
        return MultiServerMCPClient({"upwork": {"transport": "streamable_http", "url": self.cfg["mcp_url"], "headers": {"Authorization": f"Bearer {token}"}}})

    async def _discover(self, client) -> dict[str, str]:
        async with client.session("upwork") as s:
            self._available = [t.name for t in (await s.list_tools()).tools]
        out = {}
        for method, groups in KEYWORDS.items():
            pinned = (self.cfg.get("tool_map") or {}).get(method)
            if pinned:
                out[method] = pinned; continue
            for words in groups:
                hit = next((n for n in self._available if all(w in n.lower() for w in words)), None)
                if hit:
                    out[method] = hit; break
        return out

    async def _call(self, method: str, args: dict) -> Any:
        async with self._lock:                                   # one request at a time + minimum spacing
            wait = self._min_interval - (asyncio.get_event_loop().time() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                client = await self._client()
                if self._tools is None:
                    self._tools = await self._discover(client)
                name = self._tools.get(method)
                if not name:
                    raise NotImplementedError(f"Upwork MCP exposes no tool for '{method}' (available: {self._available})")
                async with client.session("upwork") as s:
                    res = await asyncio.wait_for(s.call_tool(name, args), self.timeout)
            except (OSError, asyncio.TimeoutError) as e:
                raise MarketplaceUnavailable(f"upwork: {e}") from e
            finally:
                self._last = asyncio.get_event_loop().time()
        if res.isError:
            raise ValueError(res.content[0].text if res.content else "upwork tool error")
        if res.structuredContent is not None:
            sc = res.structuredContent
            return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
        txt = res.content[0].text if res.content else "null"
        try:
            return json.loads(txt)
        except ValueError:
            return {"text": txt}

    # ---- MarketplacePort ----------------------------------------------------------------------------------
    async def search_jobs(self, query: str, limit: int = 20):
        r = await self._call("search_jobs", {"query": query, "limit": limit})
        return r if isinstance(r, list) else r.get("items") or r.get("jobs") or []

    async def get_job(self, job_id: str):
        return await self._call("get_job", {"job_id": job_id})

    async def get_client_history(self, client_id: str):
        return await self._call("get_client_history", {"client_id": client_id})

    async def get_connects_balance(self):
        return await self._call("get_connects_balance", {})

    async def list_messages(self, proposal_id: str):
        r = await self._call("list_messages", {"proposal_id": proposal_id})
        return r if isinstance(r, list) else r.get("items") or r.get("messages") or []

    async def create_proposal_draft(self, payload: dict, idempotency_key: str, dry_run: bool = False):
        if dry_run:
            return {"dry_run": True, "would_send": payload, "note": "live mode creates a DRAFT on Upwork; you confirm it there"}
        return {**(await self._call("create_proposal_draft", {**payload, "idempotency_key": idempotency_key})), "draft_only": True}

    async def submit_proposal(self, proposal_id: str, idempotency_key: str):
        """Live mode NEVER submits. The user confirms the draft on Upwork, as the platform requires."""
        return {"proposal_id": proposal_id, "status": "draft_pending_user_confirmation", "outcome": None,
                "message": "Open the draft on Upwork and confirm it there. GigBid will not submit on your behalf."}

    async def send_message(self, proposal_id: str, text: str, idempotency_key: str):
        return {**(await self._call("send_message", {"proposal_id": proposal_id, "text": text, "idempotency_key": idempotency_key})), "draft_only": True}
