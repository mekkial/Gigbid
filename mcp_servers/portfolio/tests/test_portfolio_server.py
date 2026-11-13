import json

from mcp.shared.memory import create_connected_server_and_client_session as connect

from mcp_servers.portfolio.server import mcp


async def test_tools_listed_with_readonly_annotations():
    async with connect(mcp._mcp_server) as c:
        tl = (await c.list_tools()).tools
        assert {t.name for t in tl} == {"search_evidence", "get_case_study", "list_skills"}
        assert all(t.annotations.readOnlyHint for t in tl)
        assert all(t.outputSchema for t in tl)


async def test_search_evidence_returns_typed_items_with_metadata():
    async with connect(mcp._mcp_server) as c:
        r = await c.call_tool("search_evidence", {"requirement": "PyTorch text classifier", "k": 3})
        items = r.structuredContent["result"]
        assert 1 <= len(items) <= 3 and {"id", "type", "source", "date", "outcome"} <= set(items[0])
        r2 = await c.call_tool("search_evidence", {"requirement": "model", "k": 5, "filters": {"skill": "PyTorch"}})
        assert all("PyTorch" in i["skills"] for i in r2.structuredContent["result"])


async def test_case_study_resource_and_unknown_id_error():
    async with connect(mcp._mcp_server) as c:
        templates = [t.uriTemplate for t in (await c.list_resource_templates()).resourceTemplates]
        assert "portfolio://case/{id}" in templates and "portfolio://proposal/{id}" in templates
        res = await c.read_resource("portfolio://case/churn-prediction")
        assert json.loads(res.contents[0].text)["id"] == "churn-prediction"
        bad = await c.call_tool("get_case_study", {"id": "nope"})
        assert bad.isError


async def test_prompts_available():
    async with connect(mcp._mcp_server) as c:
        names = {p.name for p in (await c.list_prompts()).prompts}
        assert {"answer_screening_question", "summarise_fit", "draft_cover_letter"} <= names
