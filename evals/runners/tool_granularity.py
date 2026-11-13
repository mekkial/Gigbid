"""R&D question A: does tool granularity change agent behaviour?
40 tasks with known-correct first calls x 3 toolsets (many fine-grained tools / few coarse tools / our tuned set with rewritten
descriptions) x 2 model sizes. Metrics: tool-selection accuracy, argument accuracy (expected values appear in the call's arguments,
so tool/parameter naming is not penalised), prompt tokens per task. Run: python -m evals.runners.tool_granularity"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")
from agent.llm import THROTTLE, load_config, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
from agent.prompts import load_prompt  # noqa: E402

SYSTEM = load_prompt("tool_eval")


def fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props or {}, "required": required or list((props or {}).keys())}}}


S = {"type": "string"}
# ---------------------------------------------------------------- toolset 1: fine-grained (terse descriptions)
FINE = [
    fn("get_job_title", "Get job title.", {"job_id": S}), fn("get_job_description", "Get job description.", {"job_id": S}),
    fn("get_job_skills", "Get job skills.", {"job_id": S}), fn("get_job_budget", "Get job budget.", {"job_id": S}),
    fn("get_job_connects_cost", "Get Connects cost of job.", {"job_id": S}), fn("get_job_posted_date", "Get job posted date.", {"job_id": S}),
    fn("get_client_spend", "Get client total spend.", {"client_id": S}), fn("get_client_rating", "Get client rating.", {"client_id": S}),
    fn("get_client_hire_rate", "Get client hire rate.", {"client_id": S}), fn("get_client_payment_verified", "Is client payment verified.", {"client_id": S}),
    fn("get_client_industry", "Get client industry.", {"client_id": S}), fn("get_connects_balance", "Get Connects balance."),
    fn("search_jobs_by_keyword", "Search jobs by keyword.", {"keyword": S}), fn("search_jobs_by_skill", "Search jobs by skill.", {"skill": S}),
    fn("search_jobs_by_budget", "Search jobs by budget.", {"min_budget": S}), fn("get_proposal_status", "Get proposal status.", {"proposal_id": S}),
    fn("list_messages", "List messages.", {"proposal_id": S}), fn("get_last_message", "Get last message.", {"proposal_id": S}),
    fn("search_portfolio_by_skill", "Search portfolio by skill.", {"skill": S}), fn("search_portfolio_by_text", "Search portfolio by text.", {"text": S}),
    fn("search_portfolio_by_industry", "Search portfolio by industry.", {"industry": S}), fn("get_case_study_title", "Get case study title.", {"id": S}),
    fn("get_case_study_text", "Get case study text.", {"id": S}), fn("get_case_study_skills", "Get case study skills.", {"id": S}),
    fn("list_skills", "List skills."), fn("get_market_median_fixed", "Median fixed price.", {"category": S}), fn("get_market_median_hourly", "Median hourly rate.", {"category": S}),
    fn("get_market_p25", "25th percentile price.", {"category": S}), fn("get_market_p75", "75th percentile price.", {"category": S}),
    fn("free_slots_this_week", "Free slots this week."), fn("free_slots_next_week", "Free slots next week."), fn("hold_slot", "Hold a slot.", {"slot": S, "title": S}),
    fn("create_email_draft", "Create email draft.", {"to": S, "subject": S, "body": S}), fn("create_proposal_draft", "Create proposal draft.", {"job_id": S, "bid_amount": S}),
    fn("dry_run_proposal", "Dry run a proposal.", {"job_id": S, "bid_amount": S}), fn("submit_proposal", "Submit proposal.", {"proposal_id": S}), fn("send_message", "Send message.", {"proposal_id": S, "text": S}),
]
# ---------------------------------------------------------------- toolset 2: coarse (4 tools, action + params)
def coarse(name, desc, actions):
    return fn(name, f"{desc} Actions: {', '.join(actions)}.", {"action": {"type": "string", "enum": actions}, "params": {"type": "object"}}, ["action", "params"])


COARSE = [coarse("marketplace", "Everything about jobs, clients, Connects, proposals and messages.", ["search_jobs", "get_job", "get_client_history", "get_connects_balance", "list_messages", "create_proposal_draft", "submit_proposal", "send_message", "get_market_stats"]),
          coarse("portfolio", "The freelancer's portfolio.", ["search_evidence", "get_case_study", "list_skills"]),
          coarse("workspace", "Calendar and email.", ["free_slots", "create_tentative_hold", "create_email_draft"]),
          coarse("misc", "Anything else.", ["help"])]


# ---------------------------------------------------------------- toolset 3: ours (the real MCP tool surface, rewritten descriptions)
def tuned_from_snapshots():
    tools = []
    for f in sorted((ROOT / "tests/contract/snapshots").glob("*.json")):
        for name, t in json.loads(f.read_text())["tools"].items():
            sch = {k: v for k, v in t["input"].items() if k in ("type", "properties", "required")}
            sch["properties"] = {k: {kk: vv for kk, vv in v.items() if kk in ("type", "description", "enum")} for k, v in sch.get("properties", {}).items() if k not in ("ctx",)}
            sch["required"] = [r for r in sch.get("required", []) if r in sch["properties"]]
            tools.append({"type": "function", "function": {"name": name, "description": t["description"], "parameters": sch}})
    return tools


JOBS = ["ai_ml-job-0003", "fullstack-job-0021", "data_analyst-job-0007", "ai_ml-job-0044"]
CLIENTS = ["client-012", "client-044", "client-071"]
KW = ["dashboard", "chatbot", "react", "dbt"]
CATS = ["ai_ml", "fullstack", "data_analyst"]
SKILLS = ["Hugging Face", "Stripe", "Power BI"]
CASES = ["churn-prediction", "shop-storefront", "warehouse-dbt"]
PROPS = ["prop-3fa81c9d2e", "prop-77b0aa12cc", "prop-0912dd4a5b"]
SLOTS = ["Tue 2026-11-17 10:00", "Wed 2026-11-18 15:00", "Thu 2026-11-19 11:00"]
EMAILS = ["maria@acme.io", "lee@northwind.com", "sam@fintrack.co"]


def build_tasks() -> list[dict]:
    """Each task: text, expected tool(s) per toolset, expected values that must appear in the arguments."""
    T = []
    def add(text, tuned, fine, coarse_, values): T.append({"text": text, "tuned": tuned, "fine": fine, "coarse": coarse_, "values": values})
    for j in JOBS[:3]:
        add(f"What is the budget for job {j}?", ["get_job"], ["get_job_budget"], [("marketplace", "get_job")], [j])
        add(f"Which skills does job {j} require?", ["get_job"], ["get_job_skills"], [("marketplace", "get_job")], [j])
    for j in JOBS[:3]:
        add(f"How many Connects will it cost me to apply to {j}?", ["get_job"], ["get_job_connects_cost"], [("marketplace", "get_job")], [j])
    for c in CLIENTS:
        add(f"Is client {c} reliable? Look at their spend and rating.", ["get_client_history"], ["get_client_spend", "get_client_rating"], [("marketplace", "get_client_history")], [c])
    for k in KW[:3]:
        add(f"Find open jobs about {k}.", ["search_jobs"], ["search_jobs_by_keyword", "search_jobs_by_skill"], [("marketplace", "search_jobs")], [k])
    for c in CATS:
        add(f"What do {c} jobs usually pay?", ["get_market_stats"], ["get_market_median_fixed", "get_market_median_hourly", "get_market_p25", "get_market_p75"], [("marketplace", "get_market_stats")], [c])
    for s in SKILLS:
        add(f"Do I have any experience with {s}?", ["search_evidence"], ["search_portfolio_by_skill", "search_portfolio_by_text"], [("portfolio", "search_evidence")], [s])
    for cs in CASES:
        add(f"Show me the full write-up of my case study {cs}.", ["get_case_study"], ["get_case_study_text"], [("portfolio", "get_case_study")], [cs])
    for sl in SLOTS:
        add(f"Hold {sl} for an interview with Acme Corp.", ["create_tentative_hold"], ["hold_slot"], [("workspace", "create_tentative_hold")], [sl])
    for j, amt in zip(JOBS[:3], (450, 900, 1200)):
        add(f"Without sending anything, preview what proposal for {j} at a bid of ${amt} would cost in Connects.", ["create_proposal_draft"], ["dry_run_proposal"], [("marketplace", "create_proposal_draft")], [j, str(amt)])
    for p in PROPS:
        add(f"Show the latest messages on proposal {p}.", ["list_messages"], ["list_messages", "get_last_message"], [("marketplace", "list_messages")], [p])
    for e in EMAILS:
        add(f"Draft an email to {e} thanking them for the interview.", ["create_email_draft"], ["create_email_draft"], [("workspace", "create_email_draft")], [e])
    add("How many Connects do I have left?", ["get_connects_balance"], ["get_connects_balance"], [("marketplace", "get_connects_balance")], [])
    add("List every skill in my portfolio.", ["list_skills"], ["list_skills"], [("portfolio", "list_skills")], [])
    add("Suggest some interview times for next week.", ["free_slots"], ["free_slots_next_week", "free_slots_this_week"], [("workspace", "free_slots")], [])
    add("What are the available slots on my calendar?", ["free_slots"], ["free_slots_next_week", "free_slots_this_week"], [("workspace", "free_slots")], [])
    return T


def score(task, toolset, call):
    """(tool_ok, args_ok) for the first tool call; arguments are value-matched so naming differences are not penalised."""
    if call is None:
        return False, False
    name, args = call
    blob = json.dumps(args).lower()
    if toolset == "coarse":
        ok = any(name == t and str(args.get("action", "")).lower() == a for t, a in task["coarse"])
    else:
        ok = name in task[toolset]
    return ok, ok and all(v.lower() in blob for v in task["values"])


def run(tier: str, toolsets: dict, tasks: list[dict]) -> dict:
    r = resolve("scout" if tier == "small" else "critic")      # small = gpt-oss-20b, "strong" here = qwen3.8-27b (the 120b budget is reserved for writer/eval runs)
    client = OpenAI(base_url=r["base_url"], api_key=os.environ[r["key_env"]], timeout=90)
    out = {}
    for ts, tools in toolsets.items():
        tool_ok = arg_ok = ptoks = api_err = 0; fails = []
        for t in tasks:
            for attempt in range(4):
                try:
                    slot = THROTTLE.acquire(r["model"], len(json.dumps(tools)) // 3 + 900, load_config()["models"]["rate_limits"]["tokens_per_minute"])
                    res = client.chat.completions.create(model=r["model"], temperature=0, tools=tools, tool_choice="auto",
                                                         messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": t["text"]}])
                    THROTTLE.settle(r["model"], slot, res.usage.total_tokens)
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(2 ** attempt)
                    res = None
            api_err += res is None
            time.sleep(0.4)
            call = None
            if res and res.choices[0].message.tool_calls:
                tc = res.choices[0].message.tool_calls[0]
                try: call = (tc.function.name, json.loads(tc.function.arguments or "{}"))
                except ValueError: call = (tc.function.name, {})
            a, b = score(t, ts, call)
            tool_ok += a; arg_ok += b; ptoks += res.usage.prompt_tokens if res else 0
            if not a: fails.append({"task": t["text"], "got": call[0] if call else None})
        n = len(tasks)
        out[ts] = {"n_tools": len(tools), "tool_selection_accuracy": round(tool_ok / n, 3), "argument_accuracy": round(arg_ok / n, 3),
                   "prompt_tokens_per_task": round(ptoks / n), "api_errors": api_err, "example_failures": fails[:4]}
        print(tier, ts, {k: v for k, v in out[ts].items() if k != "example_failures"}, flush=True)
    return {"model": r["model"], "toolsets": out}


def main():
    tasks = build_tasks()
    assert len(tasks) == 40, len(tasks)
    sets = {"fine_grained": FINE, "coarse": COARSE, "tuned": tuned_from_snapshots()}
    # per-toolset key names used by score(): fine->'fine', coarse->'coarse', tuned->'tuned'
    key = {"fine_grained": "fine", "coarse": "coarse", "tuned": "tuned"}
    res = {"n_tasks": len(tasks), "hypothesis": "see docs/adr/0003-tool-granularity.md", "results": {}}
    for tier in ("strong", "small"):
        wrapped = {key[k]: v for k, v in sets.items()}
        res["results"][tier] = run(tier, wrapped, tasks)
    (ROOT / "evals/results/tool_granularity.json").write_text(json.dumps(res, indent=2)); print("wrote tool_granularity.json")


if __name__ == "__main__":
    main()
