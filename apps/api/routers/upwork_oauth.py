"""Upwork OAuth 2.1 (authorization code + PKCE) per the MCP authorization spec: protected-resource discovery -> authorization-server
metadata -> dynamic client registration (RFC 7591) -> authorize -> token exchange. Tokens are stored ENCRYPTED per user (never logged,
never returned). STATUS: spec-conformant and unit-tested with mocked endpoints; not run against the real Upwork server (needs an account)."""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from agent.llm import load_config
from apps.api import db
from apps.api.auth import vault
from apps.api.auth.security import current_user

router = APIRouter(tags=["oauth"])
PENDING: dict[str, dict] = {}                     # state -> {user_id, verifier, client_id, token_endpoint, redirect_uri}; short-lived, in-memory


def redirect_uri() -> str:
    return os.environ.get("PUBLIC_API_URL", "http://localhost:8000") + "/api/oauth/upwork/callback"


async def discover(http: httpx.AsyncClient) -> dict:
    base = load_config()["marketplace"]["live"]["mcp_url"].rsplit("/mcp", 1)[0]
    prm = (await http.get(f"{base}/.well-known/oauth-protected-resource")).json()
    issuer = prm["authorization_servers"][0]
    meta = (await http.get(f"{issuer.rstrip('/')}/.well-known/oauth-authorization-server")).json()
    return meta


async def register_client(http: httpx.AsyncClient, meta: dict) -> str:
    if os.environ.get("UPWORK_CLIENT_ID"):                       # pre-registered client wins
        return os.environ["UPWORK_CLIENT_ID"]
    r = await http.post(meta["registration_endpoint"], json={"client_name": "GigBid", "redirect_uris": [redirect_uri()], "grant_types": ["authorization_code", "refresh_token"],
                                                             "response_types": ["code"], "token_endpoint_auth_method": "none"})
    r.raise_for_status()
    return r.json()["client_id"]


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@router.get("/oauth/upwork/start")
async def start(user: dict = Depends(current_user), http: httpx.AsyncClient = Depends(lambda: httpx.AsyncClient(timeout=20))):
    async with http:
        meta = await discover(http)
        client_id = await register_client(http, meta)
    verifier, challenge = pkce()
    state = secrets.token_urlsafe(24)
    PENDING[state] = {"user_id": user["id"], "verifier": verifier, "client_id": client_id, "token_endpoint": meta["token_endpoint"], "ts": time.time()}
    q = httpx.QueryParams({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri(), "state": state, "code_challenge": challenge,
                           "code_challenge_method": "S256", "resource": load_config()["marketplace"]["live"]["mcp_url"]})
    return {"authorize_url": f"{meta['authorization_endpoint']}?{q}"}


@router.get("/oauth/upwork/callback")
async def callback(code: str, state: str, http: httpx.AsyncClient = Depends(lambda: httpx.AsyncClient(timeout=20))):
    p = PENDING.pop(state, None)
    if not p or time.time() - p["ts"] > 600:
        raise HTTPException(400, "unknown or expired state")
    async with http:
        r = await http.post(p["token_endpoint"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(), "client_id": p["client_id"],
                                                       "code_verifier": p["verifier"], "resource": load_config()["marketplace"]["live"]["mcp_url"]})
    if r.status_code >= 400:
        raise HTTPException(400, "token exchange failed")
    await vault.save_token(p["user_id"], "upwork", {**r.json(), "client_id": p["client_id"], "obtained_at": time.time()})
    return RedirectResponse(os.environ.get("PUBLIC_WEB_URL", "/") + "settings?connected=upwork")


@router.delete("/oauth/upwork")
async def disconnect(user: dict = Depends(current_user)):
    await db.run("DELETE FROM oauth_tokens WHERE user_id=%s AND provider='upwork'", user["id"])
    return {"disconnected": True}
