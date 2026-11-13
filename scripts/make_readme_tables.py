"""Regenerate the result tables inside README.md from evals/results/*.json, so every number in the README traces to a results file.
  python scripts/make_readme_tables.py           rewrite README.md
  python scripts/make_readme_tables.py --check   exit 1 if README.md is out of date (CI)"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
R = ROOT / "evals/results"


def load(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def rag():
    d = load("rag_eval.json")
    if not d: return "_not run yet (`make eval`)_"
    rows = [[v, p["macro"]["recall@5"], p["macro"]["mrr"], p["macro"]["ndcg@10"], p["macro"]["p95_s"],
             "/".join(str(p[x]["abstain_rate_on_skip_jobs"]) for x in ("ai_ml", "fullstack", "data_analyst"))] for v, p in d["variants"].items()]
    return f"_n = {d['config']['n_per_persona']} jobs per persona, macro-average over 3 personas; source `evals/results/rag_eval.json`_\n\n" + table(["variant", "Recall@5", "MRR", "nDCG@10", "p95 s/query", "abstain on skip jobs (per persona)"], rows)


def ablation():
    d = load("rag_ablation.json")
    if not d: return "_not run yet_"
    rows = [[k, v["macro"]["recall@5"], v["macro"]["mrr"], v["macro"]["ndcg@10"]] for k, v in d["runs"].items()]
    return table(["pipeline", "Recall@5", "MRR", "nDCG@10"], rows)


def proposals():
    d = load("proposal_eval.json")
    if not d: return "_not run yet_"
    rows = []
    for v, x in d["variants"].items():
        o = x["overall"]
        rows.append([v, o["n_proposals"], f"{o['reply_rate']} {o['reply_ci95']}", o["unsupported_rate_before_verification"], o["unsupported_rate_after_verification"], o["ungrounded_numbers_per_proposal"],
                     o["judge_overall_mean"], o["p95_latency_s"], o["list_cost_usd_per_proposal"]])
    return table(["variant", "n", "GigSim reply rate (95% CI)", "unsupported before", "unsupported after", "ungrounded numbers/proposal", "judge (uncalibrated)", "p95 latency s", "list cost USD/proposal"], rows)


def arch():
    d = load("arch_compare.json")
    if not d: return "_not run yet_"
    rows = [[k, v["n_jobs"], v["decision_accuracy"], v["unsupported_claim_rate_mean"], v["proposals_with_raw_policy_violation"], v["gigsim_reply_rate"], v["p95_latency_s"], v["tokens_per_job"], v["list_cost_usd_per_job"]] for k, v in d["architectures"].items()]
    return table(["architecture", "n jobs", "bid/skip accuracy", "unsupported claim rate", "proposals w/ raw policy violation", "reply rate", "p95 s", "tokens/job", "list USD/job"], rows)


def tools():
    d = load("tool_granularity.json")
    if not d: return "_not run yet_"
    rows = [[tier, r["model"], ts, t["n_tools"], t["tool_selection_accuracy"], t["argument_accuracy"], t["prompt_tokens_per_task"]] for tier, r in d["results"].items() for ts, t in r["toolsets"].items()]
    return table(["tier", "model", "toolset", "tools", "tool-selection acc", "argument acc", "prompt tokens/task"], rows)


def injection():
    d = load("injection_eval.json")
    if not d: return "_not run yet_"
    rows = []
    for kind, key in (("job posts", "jobs"), ("client messages", "client_messages")):
        for cond, x in d[key].items():
            rows.append([kind, cond, x["n"], x.get("asr_raw_writer_output", x.get("asr_raw_liaison_output")), x["asr_after_compliance_guard"]])
    return table(["attack surface", "condition", "n", "ASR raw model output", "ASR after Compliance Guard"], rows)


SECTIONS = {"rag": rag, "ablation": ablation, "proposals": proposals, "arch": arch, "tools": tools, "injection": injection}


def render(text):
    for name, fn in SECTIONS.items():
        text = re.sub(rf"(<!-- BEGIN:{name} -->).*?(<!-- END:{name} -->)", lambda m: f"{m.group(1)}\n{fn()}\n{m.group(2)}", text, flags=re.S)
    return text


if __name__ == "__main__":
    readme = ROOT / "README.md"; cur = readme.read_text(); new = render(cur)
    if "--check" in sys.argv:
        if cur != new: print("README.md tables are out of date: run python scripts/make_readme_tables.py"); sys.exit(1)
        print("ok: README tables match evals/results"); sys.exit(0)
    readme.write_text(new); print("README tables updated")
