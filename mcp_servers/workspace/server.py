"""GigBid Workspace MCP server: free calendar slots, tentative interview holds, email drafts (local mock backend)."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

mcp = FastMCP("gigbid-workspace", instructions="Calendar slots and email drafts. Nothing is ever sent; drafts and holds only.")
STORE = Path(os.environ.get("WORKSPACE_STORE", ".local/workspace.json"))
BUSY = {(1, 14), (2, 10), (3, 16)}      # (weekday, hour) blocks in the mock calendar


def _load() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {"holds": [], "drafts": []}


def _save(d: dict):
    STORE.parent.mkdir(parents=True, exist_ok=True); STORE.write_text(json.dumps(d, indent=2))


class Hold(BaseModel):
    hold_id: str
    slot: str
    title: str
    status: str = "tentative"


class EmailDraft(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str
    status: str = "draft"


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, destructiveHint=False),
          description="List free 30-minute interview slots in the next N days (business hours, Mon-Fri).")
def free_slots(days: Annotated[int, Field(ge=1, le=14)] = 5, max_slots: Annotated[int, Field(ge=1, le=20)] = 6) -> list[str]:
    held = {h["slot"] for h in _load()["holds"]}
    out, d = [], datetime.now().replace(minute=0, second=0, microsecond=0)
    for i in range(1, days + 1):
        day = d + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        for hour in (10, 11, 14, 15, 16):
            s = day.replace(hour=hour).strftime("%a %Y-%m-%d %H:%M")
            if (day.weekday(), hour) not in BUSY and s not in held:
                out.append(s)
    return out[:max_slots]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, destructiveHint=False),
          description="Create a TENTATIVE hold for an interview slot (not confirmed with anyone). Same slot+title returns the existing hold.")
def create_tentative_hold(slot: Annotated[str, Field(min_length=8, max_length=40)], title: Annotated[str, Field(min_length=3, max_length=120)]) -> Hold:
    d = _load()
    for h in d["holds"]:
        if h["slot"] == slot and h["title"] == title:
            return Hold(**h)
    h = Hold(hold_id="hold-" + uuid.uuid4().hex[:8], slot=slot, title=title)
    d["holds"].append(h.model_dump()); _save(d)
    return h


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False, destructiveHint=False),
          description="Create an email DRAFT in the user's mailbox. It is never sent by this server.")
def create_email_draft(to: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")], subject: Annotated[str, Field(min_length=1, max_length=200)],
                       body: Annotated[str, Field(min_length=1, max_length=5000)]) -> EmailDraft:
    d = _load(); e = EmailDraft(draft_id="draft-" + uuid.uuid4().hex[:8], to=to, subject=subject, body=body)
    d["drafts"].append(e.model_dump()); _save(d)
    return e


def main():
    mcp.run()


if __name__ == "__main__":
    main()
