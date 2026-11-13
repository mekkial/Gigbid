from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from apps.api import db
from apps.api.auth import vault
from apps.api.auth.security import current_user, hash_password, make_token, verify_password
from apps.api.schemas.models import LoginIn, RegisterIn, Settings, SettingsIn, TokenOut, UserOut

router = APIRouter(tags=["auth"])


def _out(u: dict, connected: list[str]) -> UserOut:
    return UserOut(id=u["id"], email=u["email"], persona=u["persona"], settings=Settings(**(u["settings"] or {})), connected=connected)


@router.post("/auth/register", response_model=TokenOut)
async def register(body: RegisterIn):
    if await db.one("SELECT 1 FROM users WHERE email=%s", body.email.lower()):
        raise HTTPException(409, "email already registered")
    uid = "u_" + uuid.uuid4().hex[:10]
    await db.run("INSERT INTO users(id,email,pw_hash,persona,settings) VALUES(%s,%s,%s,%s,%s)", uid, body.email.lower(),
                 hash_password(body.password), body.persona, db.J(Settings().model_dump()))
    return TokenOut(access_token=make_token(uid))


@router.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn):
    u = await db.one("SELECT id, pw_hash FROM users WHERE email=%s", body.email.lower())
    if not u or not verify_password(body.password, u["pw_hash"]):
        raise HTTPException(401, "wrong email or password")
    return TokenOut(access_token=make_token(u["id"]))


@router.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return _out(user, await vault.connected(user["id"]))


@router.put("/settings", response_model=UserOut)
async def update_settings(body: SettingsIn, user: dict = Depends(current_user)):
    persona = body.persona or user["persona"]
    settings = (body.settings or Settings(**(user["settings"] or {}))).model_dump()
    await db.run("UPDATE users SET persona=%s, settings=%s WHERE id=%s", persona, db.J(settings), user["id"])
    return _out({**user, "persona": persona, "settings": settings}, await vault.connected(user["id"]))
