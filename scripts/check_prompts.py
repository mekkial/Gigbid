"""CI rule: every prompt lives in agent/prompts/*.md. Fails if python code under agent/, apps/, rag/, evals/, worker/ contains an inline
prompt-like string (second-person instruction text) instead of load_prompt(...). Heuristic: string literals > 80 chars that start with
'You are' / 'Rewrite' / 'Return ONLY' / 'Split the' etc."""
import ast, pathlib, re, sys

PAT = re.compile(r"^\s*(you are|you must|rewrite one|split the|return only|decide whether|classify)", re.I)
bad = []
for root in ("agent", "apps", "rag", "evals", "worker", "mcp_servers"):
    for f in pathlib.Path(root).rglob("*.py"):
        tree = ast.parse(f.read_text())
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
        for node in ast.walk(tree):
            if id(node) in docs:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) > 80 and PAT.match(node.value):
                bad.append(f"{f}:{node.lineno}: {node.value[:60]!r}")
if bad:
    print("Inline prompts found (move to agent/prompts/):\n" + "\n".join(bad)); sys.exit(1)
print("ok: no inline prompts")
