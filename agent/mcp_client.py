"""MCP client: MultiServerMCPClient with persistent sessions, per-agent tool allowlists (A6), per-call timeouts,
bounded retries with backoff, and a degraded mode that the UI can display and that recovers on its own."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.marketplace_port import MarketplaceUnavailable
from agent.tools import NODE_TOOL_ALLOWLIST, ToolNotAllowed

TOOL_SERVER = {
    **{t: "portfolio" for t in ("search_evidence", "get_case_study", "list_skills")},
    **{t: "marketplace" for t in ("search_jobs", "get_job", "get_client_history", "get_connects_balance", "list_messages", "get_market_stats",
                                  "create_proposal_draft", "submit_proposal", "send_message")},
    **{t: "workspace" for t in ("free_slots", "create_tentative_hold", "create_email_draft")},
}


def default_connections(persona: str = "ai_ml", marketplace_url: str | None = None, token: str | None = None,
                        trace_id: str | None = None) -> dict:
    py = sys.executable
    env = {**os.environ, "GIGBID_PERSONA": persona}
    headers = {"Authorization": f"Bearer {token or os.environ.get('MARKETPLACE_MCP_TOKEN', 'dev-mcp-token')}"}
    if trace_id:
        headers["x-trace-id"] = trace_id
    return {
        "portfolio": {"transport": "stdio", "command": py, "args": ["-m", "mcp_servers.portfolio.server"], "env": env},
        "workspace": {"transport": "stdio", "command": py, "args": ["-m", "mcp_servers.workspace.server"], "env": env},
        "marketplace": {"transport": "streamable_http", "url": marketplace_url or os.environ.get("MARKETPLACE_MCP_URL", "http://127.0.0.1:8082/mcp"),
                        "headers": headers},
    }


class MCPToolbox:
    def __init__(self, connections: dict, timeout: float = 30.0, retries: int = 2, backoff: float = 0.5, cooldown: float = 3.0):
        self.persona = connections.get("portfolio", {}).get("env", {}).get("GIGBID_PERSONA", "ai_ml")
        self.client = MultiServerMCPClient(connections)
        self.names = list(connections)
        self.timeout, self.retries, self.backoff, self.cooldown = timeout, retries, backoff, cooldown
        self.sessions: dict[str, Any] = {}
        self._stacks: dict[str, contextlib.AsyncExitStack] = {}
        self.status: dict[str, dict] = {n: {"up": False, "since": time.time(), "error": None} for n in connections}
        self._lock = asyncio.Lock()

    # --- connection management -------------------------------------------------------------------------------
    async def _connect(self, name: str):
        stack = contextlib.AsyncExitStack()
        try:
            session = await asyncio.wait_for(stack.enter_async_context(self.client.session(name)), self.timeout)
        except BaseException:
            await stack.aclose()
            raise
        self.sessions[name], self._stacks[name] = session, stack
        self.status[name] = {"up": True, "since": time.time(), "error": None}

    async def start(self):
        await asyncio.gather(*[self._ensure(n) for n in self.names], return_exceptions=True)
        return self

    async def _drop(self, name: str, err: str):
        self.sessions.pop(name, None)
        st = self._stacks.pop(name, None)
        if st:
            with contextlib.suppress(BaseException):
                await st.aclose()
        self.status[name] = {"up": False, "since": time.time(), "error": err}

    async def _ensure(self, name: str):
        if name in self.sessions:
            return self.sessions[name]
        async with self._lock:
            if name in self.sessions:
                return self.sessions[name]
            last = self.status[name]
            if not last["up"] and last["error"] and time.time() - last["since"] < self.cooldown:
                raise MarketplaceUnavailable(f"{name} is down: {last['error']}")     # circuit open: fail fast
            try:
                await self._connect(name)
            except BaseException as e:  # noqa: BLE001
                await self._drop(name, f"{type(e).__name__}: {e}"[:200])
                raise MarketplaceUnavailable(f"{name} unreachable") from e
            return self.sessions[name]

    def health(self) -> dict:
        """For the UI banner: per-server up/down."""
        return {n: {"up": s["up"], "error": s["error"]} for n, s in self.status.items()}

    async def stop(self):
        for n in list(self._stacks):
            await self._drop(n, "stopped")

    # --- calls -----------------------------------------------------------------------------------------------
    async def call(self, node: str, tool: str, **args: Any) -> Any:
        if tool not in NODE_TOOL_ALLOWLIST.get(node, set()):
            raise ToolNotAllowed(f"{node} may not call {tool}")
        args = self._flatten(tool, args)
        if tool == "get_market_stats" and "category" not in args:
            args = {"category": self.persona}
        server = TOOL_SERVER[tool]
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                session = await self._ensure(server)
                res = await asyncio.wait_for(session.call_tool(tool, args), self.timeout)
            except (asyncio.TimeoutError, MarketplaceUnavailable, OSError, Exception) as e:  # noqa: BLE001
                last = e
                if isinstance(e, MarketplaceUnavailable) and "down" in str(e):
                    break
                await self._drop(server, f"{type(e).__name__}: {e}"[:200])
                await asyncio.sleep(self.backoff * 2 ** attempt)
                continue
            if res.isError:
                text = res.content[0].text if res.content else "tool error"
                if "marketplace_unavailable" in text or "rate_limited" in text:
                    last = MarketplaceUnavailable(text)
                    await asyncio.sleep(self.backoff * 2 ** attempt)
                    continue
                raise ValueError(text)
            return self._unwrap(tool, res)
        raise MarketplaceUnavailable(f"{server}: {last}")

    @staticmethod
    def _flatten(tool: str, args: dict) -> dict:
        if tool == "create_proposal_draft" and "payload" in args:      # port-shaped call -> MCP tool arguments
            return {**args["payload"], "idempotency_key": args["idempotency_key"], "dry_run": args.get("dry_run", False)}
        return args

    @staticmethod
    def _unwrap(tool: str, res) -> Any:
        sc = res.structuredContent
        if sc is None:
            txt = res.content[0].text if res.content else "null"
            try:
                return json.loads(txt)
            except ValueError:
                return txt
        if set(sc) == {"result"}:
            return sc["result"]
        if tool in ("search_jobs", "list_messages"):
            return sc["items"]
        if tool in ("create_proposal_draft", "submit_proposal", "send_message"):
            return sc["data"]
        return sc
