"""Shared MCP server plumbing: bearer auth, per-user rate limiter, PII masking, idempotency + append-only audit log."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from collections import defaultdict

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
_PAY = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def mask_pii(obj):
    """Mask emails, phone numbers and card-like numbers in any JSON-able structure (R9/E4)."""
    if isinstance(obj, str):
        return _PAY.sub("[card]", _PHONE.sub("[phone]", _EMAIL.sub("[email]", obj)))
    if isinstance(obj, dict):
        return {k: mask_pii(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_pii(v) for v in obj]
    return obj


def token_map() -> dict[str, str]:
    raw = os.environ.get("MARKETPLACE_TOKENS", "dev-mcp-token:service")
    return dict(p.split(":", 1) for p in raw.split(",") if ":" in p)


def identity(ctx) -> tuple[str, str]:
    """(user, trace_id) from the HTTP request headers; in-memory transports fall back to a local identity."""
    rc = getattr(ctx, "request_context", None) if ctx is not None else None
    meta = (getattr(rc, "meta", None).model_dump() if getattr(rc, "meta", None) is not None else {}) or {}
    req = getattr(rc, "request", None)
    headers = getattr(req, "headers", None)
    trace = meta.get("trace_id") or (headers.get("x-trace-id") if headers is not None else None) or "trace-" + uuid.uuid4().hex[:8]
    if headers is None:
        return meta.get("user") or "local", trace
    user = token_map().get(headers.get("authorization", "").removeprefix("Bearer ").strip())
    if not user:
        raise PermissionError("invalid bearer token")
    if user == "service" and meta.get("user"):                 # trusted API service acts on behalf of a tenant
        user = meta["user"]
    return user, trace


class BearerAuthMiddleware:
    """ASGI middleware: reject HTTP requests without a valid bearer token before they reach MCP."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] != "/health":
            h = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            if h.get("authorization", "").removeprefix("Bearer ").strip() not in token_map():
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


class RateLimiter:
    """Per-user token bucket kept under GigSim's own limit (A2)."""

    def __init__(self, per_minute: int = 40):
        self.cap, self.rate = per_minute, per_minute / 60.0
        self.b: dict[str, tuple[float, float]] = defaultdict(lambda: (float(per_minute), time.time()))
        self.lock = threading.Lock()

    def allow(self, user: str) -> bool:
        with self.lock:
            tokens, ts = self.b[user]
            now = time.time()
            tokens = min(self.cap, tokens + (now - ts) * self.rate)
            if tokens < 1:
                self.b[user] = (tokens, now)
                return False
            self.b[user] = (tokens - 1, now)
            return True


class Ledger:
    """SQLite: idempotency results + append-only audit log (UPDATE/DELETE blocked by triggers)."""

    def __init__(self, path: str | None = None):
        path = path or os.environ.get("MCP_LEDGER_PATH", ".local/mcp_ledger.sqlite")
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS idempotency(user TEXT, tool TEXT, key TEXT, result TEXT, PRIMARY KEY(user, tool, key));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user TEXT, tool TEXT,
                                         arguments TEXT, result TEXT, trace_id TEXT);
        CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
        """)

    def get_idem(self, user, tool, key):
        with self.lock:
            r = self.db.execute("SELECT result FROM idempotency WHERE user=? AND tool=? AND key=?", (user, tool, key)).fetchone()
        return json.loads(r[0]) if r else None

    def put_idem(self, user, tool, key, result):
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO idempotency VALUES (?,?,?,?)", (user, tool, key, json.dumps(result)))

    def audit(self, user, tool, arguments, result, trace_id):
        from agent.tracing import span
        with span(f"mcp.{tool}", trace_id=trace_id, user=user):      # correlate the MCP call with the same trace id
            pass
        with self.lock, self.db:
            self.db.execute("INSERT INTO audit(ts,user,tool,arguments,result,trace_id) VALUES (?,?,?,?,?,?)",
                            (time.time(), user, tool, json.dumps(mask_pii(arguments), default=str),
                             json.dumps(mask_pii(result), default=str)[:4000], trace_id))

    def audit_rows(self, limit=100):
        with self.lock:
            return self.db.execute("SELECT ts,user,tool,arguments,result,trace_id FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
