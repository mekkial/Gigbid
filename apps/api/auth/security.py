"""Password hashing (scrypt), JWT sessions, and the current-user dependency."""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api import db

ALGO = "HS256"
bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    s = os.environ.get("APP_SECRET_KEY", "")
    if not s or s == "replace_me":
        s = "dev-only-secret-change-me-32-bytes-min!!"
    return s


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return salt.hex() + ":" + h.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt, h = stored.split(":")
    return hmac.compare_digest(hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex(), h)


def make_token(user_id: str, ttl: int = 7 * 86400) -> str:
    return jwt.encode({"sub": user_id, "exp": int(time.time()) + ttl}, _secret(), algorithm=ALGO)


async def current_user(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    token = cred.credentials if cred else request.query_params.get("token")     # EventSource cannot set headers
    if not token:
        raise HTTPException(401, "not authenticated")
    try:
        uid = jwt.decode(token, _secret(), algorithms=[ALGO])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")
    u = await db.one("SELECT id, email, persona, settings FROM users WHERE id=%s", uid)
    if not u:
        raise HTTPException(401, "unknown user")
    request.state.user_id = uid
    return u
