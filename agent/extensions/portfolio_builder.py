"""X3 Portfolio builder: GitHub repo -> case study whose every claim is verified against the code -> Portfolio server.

Pipeline: RepoSource (GitHub MCP server, or a local folder) -> facts -> LLM draft with per-claim file citations ->
deterministic verification (skills must appear in code/manifests; numbers must appear in the repo; cited files must exist) ->
LLM verifier on what remains -> only verified claims are published. Never-verified output is dropped, not softened."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agent.llm import chat_json
from agent.prompts import load_prompt, untrusted

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb", ".sql", ".yaml", ".yml", ".toml", ".json", ".md", ".sh", ".dockerfile"}
MANIFESTS = ("requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml", "Gemfile", "pom.xml", "Dockerfile", "docker-compose.yml")
MAX_FILE_CHARS, MAX_FILES = 3500, 14


class RepoSource(Protocol):
    async def tree(self, repo: str) -> list[str]: ...
    async def read(self, repo: str, path: str) -> str: ...


class LocalRepoSource:
    """A folder on disk (tests, private code that must not leave the machine)."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    async def tree(self, repo: str = "") -> list[str]:
        skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".local"}
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file() and not (set(p.parts) & skip))

    async def read(self, repo: str, path: str) -> str:
        return (self.root / path).read_text(errors="ignore")


class GitHubMCPSource:
    """The official GitHub MCP server (third-party, read-only token). Tool names are discovered by keyword, like the Upwork adapter.
    Needs GITHUB_TOKEN (fine-grained, read-only, selected repos). Not exercised against github.com in this submission's tests (fake server only)."""

    def __init__(self, token: str | None = None, url: str = "https://api.githubcopilot.com/mcp/", connection: dict | None = None):
        from langchain_mcp_adapters.client import MultiServerMCPClient
        conn = connection or {"transport": "streamable_http", "url": url, "headers": {"Authorization": f"Bearer {token or os.environ['GITHUB_TOKEN']}"}}
        self.client = MultiServerMCPClient({"github": conn}); self._tools: list[str] | None = None

    async def _call(self, words: list[str], args: dict):
        async with self.client.session("github") as s:
            names = [t.name for t in (await s.list_tools()).tools]
            name = next(n for n in names if all(w in n.lower() for w in words))
            res = await s.call_tool(name, args)
        if res.isError:
            raise ValueError(res.content[0].text)
        sc = res.structuredContent
        return sc if sc is not None else (res.content[0].text if res.content else "")

    async def tree(self, repo: str) -> list[str]:
        owner, name = repo.split("/", 1)
        r = await self._call(["get", "file"], {"owner": owner, "repo": name, "path": ""})        # directory listing
        items = r if isinstance(r, list) else json.loads(r) if isinstance(r, str) and r.strip().startswith("[") else []
        return [i["path"] if isinstance(i, dict) else str(i) for i in items]

    async def read(self, repo: str, path: str) -> str:
        owner, name = repo.split("/", 1)
        r = await self._call(["get", "file"], {"owner": owner, "repo": name, "path": path})
        return r if isinstance(r, str) else json.dumps(r)


@dataclass
class RepoFacts:
    repo: str
    files: dict[str, str] = field(default_factory=dict)
    tree: list[str] = field(default_factory=list)

    @property
    def corpus(self) -> str:
        return "\n".join([" ".join(self.tree)] + list(self.files.values())).lower()


async def gather_facts(src: RepoSource, repo: str) -> RepoFacts:
    tree = await src.tree(repo)
    def rank(p: str):                                            # README and manifests first, then shallow source files
        n = p.lower().rsplit("/", 1)[-1]
        return (0 if n.startswith("readme") else 1 if p.rsplit("/", 1)[-1] in MANIFESTS else 2, p.count("/"), len(p))
    picks = [p for p in sorted(tree, key=rank) if (Path(p).suffix.lower() in CODE_EXT or p.rsplit("/", 1)[-1] in MANIFESTS)][:MAX_FILES]
    f = RepoFacts(repo, tree=tree)
    for p in picks:
        try:
            f.files[p] = (await src.read(repo, p))[:MAX_FILE_CHARS]
        except Exception:  # noqa: BLE001 - unreadable file: skip, never guess its content
            continue
    return f


class ClaimRef(BaseModel):
    text: str
    kind: Literal["skill", "feature", "result"]
    source_paths: list[str] = Field(default_factory=list)


class DraftCase(BaseModel):
    title: str
    summary: str
    skills: list[str] = Field(default_factory=list)
    claims: list[ClaimRef] = Field(default_factory=list)


def draft(facts: RepoFacts) -> DraftCase:
    body = f"REPO: {facts.repo}\nTREE:\n" + "\n".join(facts.tree[:120]) + "\n\n" + "\n\n".join(f"--- {p}\n{t}" for p, t in facts.files.items())
    return chat_json("writer", load_prompt("portfolio_builder"), untrusted("repo", body), DraftCase)


_NUM = re.compile(r"\d+(?:\.\d+)?")


def verify_deterministic(d: DraftCase, facts: RepoFacts) -> tuple[list[ClaimRef], list[dict]]:
    corpus, kept, dropped = facts.corpus, [], []
    for c in d.claims:
        why = None
        if any(p not in facts.tree for p in c.source_paths) or (c.kind != "skill" and not c.source_paths):
            why = "cited file does not exist (or none cited)"
        elif c.kind == "skill" and c.text.lower().split("(")[0].strip() not in corpus:
            why = "technology never appears in the repo"
        elif c.kind == "result" and not _NUM.findall(c.text):
            why = "a 'result' must be measurable (contain a number); impact/business claims are never published"
        elif c.kind == "result" and any(n not in corpus for n in _NUM.findall(c.text)):
            why = "number not found anywhere in the repo"
        (dropped.append({"claim": c.text, "kind": c.kind, "reason": why}) if why else kept.append(c))
    return kept, dropped


def verify_llm(claims: list[ClaimRef], facts: RepoFacts) -> tuple[list[ClaimRef], list[dict]]:
    """Second opinion by the claim verifier node, with the cited files as evidence."""
    from rag.verify import verify_claims
    ev = [{"id": p, "type": "code", "date": "", "text": t} for p, t in facts.files.items()]
    graded = verify_claims("\n".join(f"- {c.text}" for c in claims), ev) if claims else []
    bad = {g.text.strip().lower() for g in graded if g.verdict == "unsupported"}
    kept, dropped = [], []
    for c in claims:
        (dropped.append({"claim": c.text, "kind": c.kind, "reason": "judged unsupported by the verifier"}) if c.text.strip().lower() in bad else kept.append(c))
    return kept, dropped


@dataclass
class BuiltCase:
    id: str
    title: str
    skills: list[str]
    markdown: str
    report: dict


async def build_case_study(src: RepoSource, repo: str, use_llm_verifier: bool = True, drafter=draft) -> BuiltCase:
    facts = await gather_facts(src, repo)
    d = drafter(facts)
    kept, dropped = verify_deterministic(d, facts)
    if use_llm_verifier:
        kept, dropped2 = verify_llm(kept, facts); dropped += dropped2
    skills = sorted({c.text.split("(")[0].strip() for c in kept if c.kind == "skill"})
    body = "\n".join(f"- {c.text} _(see {', '.join(c.source_paths) or 'repo'})_" for c in kept if c.kind != "skill")
    summary = d.summary if not dropped or not kept else " ".join(c.text.rstrip(".") + "." for c in kept if c.kind != "skill")[:600] or d.summary
    slug = re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")
    md = f"# {d.title}\n\nSource: {repo} (verified against the code)\n\n{summary}\n\nSkills: {', '.join(skills)}\n\n{body}\n"
    n = len(d.claims)
    return BuiltCase(id=f"gh-{slug}", title=d.title, skills=skills, markdown=md,
                     report={"repo": repo, "claims_drafted": n, "claims_published": len(kept), "claims_removed": len(dropped), "verified_rate": round(len(kept) / n, 3) if n else None, "removed": dropped})


def publish(case: BuiltCase, persona_dir: str | Path, industry: str = "software", year: int = 2025, index=None) -> None:
    """Add the verified case study to the persona's portfolio (read by the Portfolio MCP server) and index only the new item."""
    base = Path(persona_dir)
    (base / "case_studies").mkdir(parents=True, exist_ok=True)
    (base / "case_studies" / f"{case.id}.md").write_text(case.markdown)
    f = base / "case_studies.json"
    cases = json.loads(f.read_text()) if f.exists() else []
    cases = [c for c in cases if c["id"] != case.id] + [{"id": case.id, "title": case.title, "skills": case.skills, "industry": industry, "year": year,
                                                         "case_study_md": case.markdown, "readme_md": case.markdown, "code_snippet": "", "synthetic": False, "source": "x3-github"}]
    f.write_text(json.dumps(cases, indent=2))
    if index is not None:
        from rag.ingest.loaders import _chunk, _split
        index.add([_chunk(base.name, "case_study", case.id, case.skills, f"{year}-06-01", industry, t, idx=i) for i, t in enumerate(_split(case.markdown))])
