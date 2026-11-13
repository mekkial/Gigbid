import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.workspace import server as w


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "STORE", tmp_path / "ws.json")


async def test_slots_hold_is_idempotent_and_removes_slot():
    async with connect(w.mcp._mcp_server) as c:
        slots = (await c.call_tool("free_slots", {"days": 7, "max_slots": 3})).structuredContent["result"]
        assert len(slots) == 3
        h1 = (await c.call_tool("create_tentative_hold", {"slot": slots[0], "title": "Interview with Acme"})).structuredContent
        h2 = (await c.call_tool("create_tentative_hold", {"slot": slots[0], "title": "Interview with Acme"})).structuredContent
        assert h1["hold_id"] == h2["hold_id"] and h1["status"] == "tentative"
        assert slots[0] not in (await c.call_tool("free_slots", {"days": 7, "max_slots": 20})).structuredContent["result"]


async def test_email_is_draft_only_and_validates_address():
    async with connect(w.mcp._mcp_server) as c:
        d = (await c.call_tool("create_email_draft", {"to": "client@example.com", "subject": "Hi", "body": "Hello"})).structuredContent
        assert d["status"] == "draft"
        assert (await c.call_tool("create_email_draft", {"to": "not-an-email", "subject": "Hi", "body": "x"})).isError
        names = {t.name for t in (await c.list_tools()).tools}
        assert not any("send" in n for n in names)
