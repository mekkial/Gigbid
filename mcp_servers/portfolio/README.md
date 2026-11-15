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
**uvx (straight from the repository; the default retrieval downloads the embedding and reranker models on first run, about 1.5 GB):**
```bash
uvx --from git+https://github.com/mekkial/Gigbid gigbid-portfolio-mcp
```
**Docker:** `docker build -f infra/docker/python.Dockerfile -t gigbid-portfolio . && docker run -i --rm -v $PWD/my-portfolio:/portfolio -e GIGBID_PORTFOLIO_DIR=/portfolio -e GIGBID_PERSONA=me gigbid-portfolio python -m mcp_servers.portfolio.server`

**Claude Desktop** (`claude_desktop_config.json`) / **Cursor** (`.cursor/mcp.json`):
```json
{ "mcpServers": { "gigbid-portfolio": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/mekkial/Gigbid", "gigbid-portfolio-mcp"],
    "env": { "GIGBID_PERSONA": "me", "GIGBID_PORTFOLIO_DIR": "/absolute/path/to/personas" } } } }
```
Try it: ask "Answer this screening question from my portfolio: have you built a RAG chatbot?" (uses the prompt template and `search_evidence`).

## Publishing status
Published as an installable package from the public repository (https://github.com/mekkial/Gigbid); there is no PyPI release. The `uvx --from git+...` command above installs the `gigbid-portfolio-mcp` entry point. Verified over MCP (stdio): 3 tools, `search_evidence` returns results, 2 resource templates, 3 prompts. For a small install with no model download, set `RAG_VARIANT=v6_bm25` (BM25 keyword retrieval; the full hybrid + reranker retrieval is the default). Tests: `pytest mcp_servers/portfolio`.
