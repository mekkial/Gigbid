"""GigBid Portfolio MCP server (read-only). Run: python -m mcp_servers.portfolio.server  (stdio)
or `uvx gigbid-portfolio-mcp`. Env: GIGBID_PERSONA, GIGBID_PORTFOLIO_DIR."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_servers.portfolio import prompts, resources, tools

mcp = FastMCP("gigbid-portfolio", instructions="Read-only access to a freelancer's portfolio evidence. "
              "Use search_evidence before making any claim about the freelancer's experience.")
RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=RO, description="Search the portfolio for evidence that proves one requirement (skill, tool, domain). "
          "Returns items with type, source, date and outcome. Call once per requirement.")
def search_evidence(requirement: str, k: int = 5, filters: tools.Filters | None = None) -> list[tools.EvidenceItem]:
    return tools.search_evidence(requirement, max(1, min(k, 20)), filters)


@mcp.tool(annotations=RO, description="Get the full case study and README for one project id returned by search_evidence.")
def get_case_study(id: str) -> tools.CaseStudy:
    return tools.get_case_study(id)


@mcp.tool(annotations=RO, description="List every skill that appears in the portfolio.")
def list_skills() -> list[str]:
    return tools.list_skills()


mcp.resource("portfolio://case/{id}", description="Full case study as JSON")(resources.case_resource)
mcp.resource("portfolio://proposal/{id}", description="A past proposal with its outcome")(resources.proposal_resource)
mcp.prompt(description="Answer a client screening question from my portfolio")(prompts.answer_screening_question)
mcp.prompt(description="Assess my fit for a job post, requirement by requirement")(prompts.summarise_fit)
mcp.prompt(description="Draft an evidence-cited cover letter for a job post")(prompts.draft_cover_letter)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
