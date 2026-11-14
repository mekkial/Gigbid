"""GigBid API (FastAPI). Run: uvicorn apps.api.main:app --port 8000"""
from __future__ import annotations

import contextlib
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(".env")

from apps.api import db, logging_config, queue  # noqa: E402
from apps.api.routers import analytics, approvals, auth, jobs, messages, proposals, runs, settings, upwork_oauth  # noqa: E402
from apps.api.runtime import RUNTIME  # noqa: E402


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    logging_config.setup()
    await RUNTIME.start()
    await queue.init()
    yield
    await db.close()


app = FastAPI(title="GigBid API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["x-trace-id"])


@app.middleware("http")
async def trace_id(request: Request, call_next):
    """One trace id from the UI request through the API, graph, MCP servers and audit log."""
    tid = request.headers.get("x-trace-id") or "trace-" + uuid.uuid4().hex[:12]
    request.state.trace_id = tid
    resp = await call_next(request)
    resp.headers["x-trace-id"] = tid
    return resp


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gigbid-api"}


for r in (auth, jobs, runs, approvals, proposals, messages, analytics, settings, upwork_oauth):
    app.include_router(r.router, prefix="/api")


# Single-container deploy (Hugging Face Space): serve the built web app from the API so one port carries UI + /api.
_static = os.environ.get("GIGBID_STATIC_DIR")
if _static and os.path.isdir(_static):
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=os.path.join(_static, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        f = os.path.join(_static, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(_static, "index.html"))
