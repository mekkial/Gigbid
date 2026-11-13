"""Offline stack for Playwright: GigSim (:8101) + API (:8100) with deterministic LLM stand-ins (no network, no cost).
Never used for reported quality numbers."""
import os, threading

os.environ.update(DATABASE_URL="postgresql://gigbid@localhost:5433/gigbid_e2e", GIGBID_TOOLS="local", GIGBID_QUEUE="inline",
                  GIGSIM_BASE_URL="http://127.0.0.1:8101", GIGSIM_API_TOKEN="dev-token", GIGBID_E2E="1")
os.environ.pop("REDIS_URL", None)

import psycopg
adm = psycopg.connect("postgresql://gigbid@localhost:5433/postgres", autocommit=True)
adm.execute("DROP DATABASE IF EXISTS gigbid_e2e WITH (FORCE)"); adm.execute("CREATE DATABASE gigbid_e2e"); adm.close()

import uvicorn
from gigsim import app as gs
gs.RULES.update(error_rate_5xx=0.0, rate_limit_per_minute=100000); gs.RULES["connects"]["starting_balance"] = 100000
threading.Thread(target=lambda: uvicorn.run(gs.app, host="127.0.0.1", port=8101, log_level="warning"), daemon=True).start()

from apps.api import main as api_main
from agent.offline_impl import offline_impl
from langgraph.checkpoint.memory import MemorySaver
_orig = api_main.RUNTIME.start
async def start():
    r = await _orig(); r.impl = offline_impl(); r.checkpointer = MemorySaver(); return r
api_main.RUNTIME.start = start
uvicorn.run(api_main.app, host="127.0.0.1", port=8100, log_level="warning")
