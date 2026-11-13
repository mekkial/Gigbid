# GigBid Portfolio MCP server

A **read-only** MCP server that lets any MCP host (Claude Desktop, Cursor, ...) search *your* portfolio for evidence before you claim anything in a proposal.

| | |
|---|---|
| Tools | `search_evidence(requirement, k, filters)` · `get_case_study(id)` · `list_skills()` (all `readOnlyHint`) |
| Resource templates | `portfolio://case/{id}` · `portfolio://proposal/{id}` |
| Prompts | `answer_screening_question` · `summarise_fit` · `draft_cover_letter` |
| Retrieval | hybrid BM25 + dense with a cross-encoder reranker (open models, CPU) |

## Your own portfolio
Layout (one folder per persona): `case_studies.json`, `proposals.jsonl` (with `outcome`: won/replied/ignored), `profile.json`, `cv.md`, `reviews.jsonl`.
Point the server at it: `GIGBID_PORTFOLIO_DIR=/path/to/personas GIGBID_PERSONA=me`. See `data/personas/ai_ml/` for a complete example, or generate case studies from your GitHub repos with the X3 builder (`docs/EXTENSION.md`).

## Install
**uvx (straight from the repository; needs a few hundred MB for the embedding/reranker models on first run):**
```bash
uvx --from git+https://github.com/<you>/gigbid gigbid-portfolio-mcp
```
**Docker:** `docker build -f infra/docker/python.Dockerfile -t gigbid-portfolio . && docker run -i --rm -v $PWD/my-portfolio:/portfolio -e GIGBID_PORTFOLIO_DIR=/portfolio -e GIGBID_PERSONA=me gigbid-portfolio python -m mcp_servers.portfolio.server`

**Claude Desktop** (`claude_desktop_config.json`) / **Cursor** (`.cursor/mcp.json`):
```json
{ "mcpServers": { "gigbid-portfolio": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/<you>/gigbid", "gigbid-portfolio-mcp"],
    "env": { "GIGBID_PERSONA": "me", "GIGBID_PORTFOLIO_DIR": "/absolute/path/to/personas" } } } }
```
Try it: ask "Answer this screening question from my portfolio: have you built a RAG chatbot?" (uses the prompt template and `search_evidence`).

## Publishing status
Not yet published to PyPI (needs the author's PyPI account); the `uvx --from git+...` path works once the repository is public. Tests: `pytest mcp_servers/portfolio`.
