"""End-to-end: bid graph (live Groq LLM) against REAL MCP servers (portfolio+workspace over stdio, marketplace over HTTP+bearer).
Prereq: GigSim on :8081 and `python -m mcp_servers.marketplace.server` on :8082."""
import asyncio, sys, time, uuid
from dotenv import load_dotenv; load_dotenv(".env")
from langgraph.types import Command
from langgraph.store.memory import InMemoryStore
from agent.checkpoint import make_checkpointer
from agent.graphs.bid_graph import build_bid_graph
from agent.mcp_client import MCPToolbox, default_connections


async def main(job_id):
    tb = await MCPToolbox(default_connections("ai_ml", trace_id="trace-e2e-1")).start()
    try:
        await run(tb, job_id)
    finally:
        await tb.stop()


async def run(tb, job_id):
    print("health:", tb.health())
    job = await tb.call("scout", "get_job", job_id=job_id)
    graph = build_bid_graph(tb, InMemoryStore(), await make_checkpointer(url="", sqlite_path=".local/e2e.sqlite"))
    cfg = {"configurable": {"thread_id": "e2e-" + uuid.uuid4().hex[:6]}}
    t = time.time()
    out = await graph.ainvoke({"job": job, "user_id": "e2e", "persona": "ai_ml", "settings": {"floor_hourly": 30}}, cfg)
    st = await graph.aget_state(cfg)
    print(f"status={out.get('status')} next={st.next} decision={out.get('decision')} {time.time()-t:.1f}s tokens={out.get('tokens')} cost=${out.get('cost_usd',0):.5f}")
    if st.next == ("approval",):
        p = st.tasks[0].interrupts[0].value
        print("unsupported before/after:", out.get("unsupported_before"), out.get("unsupported_after"), "| dry_run:", p["dry_run"])
        print("DRAFT:", p["send_text"][:500])
        res = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
        print("submitted:", res["status"], res["outcome"].get("status"), res["outcome"].get("outcome"))
    print("trace:", [(x["node"], x["latency_s"]) for x in out["trace"]])

asyncio.run(main(sys.argv[1]))
