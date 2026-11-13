"""Schema snapshot test (A7): fails CI when any MCP tool/resource/prompt signature changes unintentionally.
Intentional change: run `UPDATE_SNAPSHOTS=1 pytest tests/contract` and commit the diff."""
import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.marketplace.server import mcp as market
from mcp_servers.portfolio.server import mcp as portfolio
from mcp_servers.workspace.server import mcp as workspace

SNAP = Path(__file__).parent / "snapshots"


async def surface(server) -> dict:
    async with connect(server._mcp_server) as c:
        tools = {t.name: {"description": t.description, "input": t.inputSchema, "output": t.outputSchema,
                          "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None}
                 for t in (await c.list_tools()).tools}
        res = sorted(t.uriTemplate for t in (await c.list_resource_templates()).resourceTemplates)
        prompts = {p.name: [a.name for a in (p.arguments or [])] for p in (await c.list_prompts()).prompts}
    return json.loads(json.dumps({"tools": tools, "resource_templates": res, "prompts": prompts}, sort_keys=True))


@pytest.mark.parametrize("name,server", [("portfolio", portfolio), ("marketplace", market), ("workspace", workspace)])
async def test_surface_matches_snapshot(name, server):
    now = await surface(server)
    f = SNAP / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOTS") or not f.exists():
        f.write_text(json.dumps(now, indent=2, sort_keys=True)); return
    assert now == json.loads(f.read_text()), f"{name} MCP tool surface changed; review and run UPDATE_SNAPSHOTS=1 if intended"
