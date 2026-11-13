# Signature extension: X3 Portfolio builder

**What it does.** Turns a GitHub repository into a portfolio case study whose claims are all verified against the code, then feeds it to the Portfolio MCP server (incremental re-index, so it is retrievable immediately).

**Pipeline** (`agent/extensions/portfolio_builder.py`)
1. `RepoSource` reads the repo: `GitHubMCPSource` (the official GitHub MCP server with a read-only token) or `LocalRepoSource` (private code stays on the machine).
2. Facts = README, file tree, dependency manifests, up to 14 source files (3.5k chars each). Repo text is wrapped as untrusted data.
3. The writer model drafts claims, each tagged `skill | feature | result` with the file paths that support it (prompt: `agent/prompts/portfolio_builder.v1.md`).
4. **Deterministic verification**: a cited file must exist; a skill must literally appear in the code/manifests/tree; a "result" must contain a number **and** that number must appear in the repo (impact claims without numbers are never published).
5. **LLM verification** of the survivors against the cited files (the same claim verifier used for proposals).
6. Only verified claims are published; the report lists every removed claim and why.

**How it is measured**
* Unit tests with a deliberately lying draft (fabricated skill, fabricated 80% result, citation of a non-existent file, injected "founded a unicorn"): all removed (`tests/unit/test_portfolio_builder.py`).
* `evals/results/x3_eval.json` (if present): claims drafted vs published, removal reasons, and retrieval Recall@5 on skill queries with vs without the generated case study. If that file is absent the experiment has not been run yet.

**Known limits.** "Verified against the code" means the claim is *present* in the code; it does not prove the freelancer wrote it (a forked repo would pass). Skills are matched by name, so a skill that is only a transitive dependency can pass. The GitHub MCP path is tested with a fake server only.
