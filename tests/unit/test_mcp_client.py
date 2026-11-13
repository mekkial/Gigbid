import asyncio
import socket
import threading
import time

import pytest
import uvicorn

from agent.marketplace_port import MarketplaceUnavailable
from agent.mcp_client import MCPToolbox
from agent.tools import ToolNotAllowed


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def conns(port):
    return {"marketplace": {"transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp",
                            "headers": {"Authorization": "Bearer dev-mcp-token"}}}


async def test_allowlist_blocks_tools_an_agent_does_not_need():
    tb = MCPToolbox(conns(free_port()))
    with pytest.raises(ToolNotAllowed):
        await tb.call("writer", "submit_proposal", proposal_id="x", idempotency_key="y" * 8)      # writer has no write tools
    with pytest.raises(ToolNotAllowed):
        await tb.call("risk_assessor", "send_message", proposal_id="x", text="hi", idempotency_key="y" * 8)


async def test_degraded_mode_reports_down_then_recovers(monkeypatch):
    from mcp_servers.marketplace import server as srv
    port = free_port()
    tb = MCPToolbox(conns(port), timeout=5, retries=1, backoff=0.05, cooldown=0.2)
    with pytest.raises(MarketplaceUnavailable):                                    # server is down
        await tb.call("pricing", "get_connects_balance")
    assert tb.health()["marketplace"]["up"] is False and tb.health()["marketplace"]["error"]

    class Fake:
        async def get_connects_balance(self): return {"balance": 7}
    monkeypatch.setattr(srv, "adapter_for", lambda user: Fake())
    server = uvicorn.Server(uvicorn.Config(srv.http_app(), host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=server.run, daemon=True); th.start()
    for _ in range(50):
        if server.started: break
        time.sleep(0.1)
    await asyncio.sleep(0.3)                                                      # past the cooldown: circuit half-opens
    res = await tb.call("pricing", "get_connects_balance")                         # auto-recovery, no restart of the client
    assert res == {"balance": 7} and tb.health()["marketplace"]["up"] is True
    await tb.stop(); server.should_exit = True
