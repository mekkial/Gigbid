"""Memory viewer (list + delete what GigBid learned), portfolio upload with incremental re-indexing, health."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from agent.memory.store import delete_item, list_items
from apps.api import db
from apps.api.auth import vault
from apps.api.auth.security import current_user
from apps.api.runtime import RUNTIME
from apps.api.schemas.models import MemoryItem, PortfolioUploadOut

router = APIRouter(tags=["settings"])
NS = {"style": "style", "outcome": "outcome"}


@router.get("/memory", response_model=list[MemoryItem])
async def memory(user: dict = Depends(current_user)):
    out = []
    for ns in ("style", "outcome"):
        out += [MemoryItem(namespace=ns, key=i["key"], value={k: v for k, v in i.items() if k != "key"}) for i in list_items(RUNTIME.store, (ns, user["id"]))]
    return out


@router.delete("/memory/{namespace}/{key:path}")
async def forget(namespace: str, key: str, user: dict = Depends(current_user)):
    if namespace not in NS:
        raise HTTPException(404, "unknown memory namespace")
    delete_item(RUNTIME.store, (namespace, user["id"]), key)
    return {"deleted": True}


@router.post("/portfolio/upload", response_model=PortfolioUploadOut)
async def upload(file: UploadFile, user: dict = Depends(current_user)):
    """Add a case study (Markdown/text) to the user's portfolio; incremental: only the new item is chunked and embedded."""
    raw = (await file.read()).decode("utf-8", "ignore")[:20000]
    if len(raw.strip()) < 40:
        raise HTTPException(422, "file too short to be a case study")
    from rag.ingest.loaders import _chunk, _split
    item_id = "up-" + uuid.uuid4().hex[:6]
    skills = sorted({s for s in re.findall(r"\b[A-Z][A-Za-z+#.]{2,}\b", raw)})[:12]
    chunks = [_chunk(user["persona"], "case_study", item_id, skills, "2025-01-01", None, t, idx=i) for i, t in enumerate(_split(raw))]
    tb = await RUNTIME.toolbox(user["persona"], user["id"])
    if hasattr(tb, "index"):
        tb.index.add(chunks)                        # LocalToolbox backend: incremental add
    d = Path(".local/uploads") / user["id"]; d.mkdir(parents=True, exist_ok=True)
    (d / f"{item_id}.json").write_text(json.dumps({"id": item_id, "chunks": chunks}))
    return PortfolioUploadOut(item_id=item_id, chunks=len(chunks))


@router.get("/health/tools")
async def health_tools(user: dict = Depends(current_user)):
    """Degraded-mode source for the UI banner: is the marketplace reachable right now?"""
    try:
        tb = await RUNTIME.toolbox(user["persona"], user["id"])
        await tb.call("pricing", "get_connects_balance")
        return {"marketplace": "up", "tools": RUNTIME.health()}
    except Exception as e:  # noqa: BLE001
        return {"marketplace": "down", "detail": str(e)[:200], "tools": RUNTIME.health()}
