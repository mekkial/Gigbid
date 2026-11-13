"""Encrypted per-user OAuth token store (Fernet). Tokens are never logged or returned by the API."""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from apps.api import db


def _key() -> bytes:
    k = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if k:
        return k.encode()
    p = Path(".local/token.key")                      # dev convenience only; production sets TOKEN_ENCRYPTION_KEY
    if not p.exists():
        p.parent.mkdir(exist_ok=True); p.write_bytes(Fernet.generate_key())
    return p.read_bytes()


async def save_token(user_id: str, provider: str, token: dict) -> None:
    enc = Fernet(_key()).encrypt(json.dumps(token).encode()).decode()
    await db.run("INSERT INTO oauth_tokens(user_id,provider,token_enc) VALUES(%s,%s,%s) "
                 "ON CONFLICT(user_id,provider) DO UPDATE SET token_enc=EXCLUDED.token_enc, updated_at=now()", user_id, provider, enc)


async def load_token(user_id: str, provider: str) -> dict | None:
    r = await db.one("SELECT token_enc FROM oauth_tokens WHERE user_id=%s AND provider=%s", user_id, provider)
    return json.loads(Fernet(_key()).decrypt(r["token_enc"].encode())) if r else None


async def connected(user_id: str) -> list[str]:
    return [r["provider"] for r in await db.fetch("SELECT provider FROM oauth_tokens WHERE user_id=%s", user_id)]
