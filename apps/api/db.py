"""Postgres access (psycopg pool). EVERY query on user data is scoped by user_id (tenant isolation, E4)."""
from __future__ import annotations

import json
import os

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

pool: AsyncConnectionPool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, persona TEXT NOT NULL DEFAULT 'ai_ml',
  settings JSONB NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS runs(
  thread_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, job_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'bid',
  status TEXT NOT NULL DEFAULT 'queued', title TEXT, category TEXT, fit REAL, risk REAL, decision TEXT, price REAL,
  connects INT, tokens INT DEFAULT 0, cost_usd REAL DEFAULT 0, latency_s REAL DEFAULT 0, proposal_id TEXT,
  outcome TEXT, summary JSONB NOT NULL DEFAULT '{}', error TEXT, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
ALTER TABLE runs ADD COLUMN IF NOT EXISTS fp TEXT;
CREATE INDEX IF NOT EXISTS runs_user ON runs(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS saved_searches(
  id SERIAL PRIMARY KEY, user_id TEXT NOT NULL, query TEXT NOT NULL, interval_min INT NOT NULL DEFAULT 180, last_run TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS oauth_tokens(
  user_id TEXT NOT NULL, provider TEXT NOT NULL, token_enc TEXT NOT NULL, updated_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(user_id, provider));
"""


async def init(url: str | None = None):
    global pool
    url = url or os.environ["DATABASE_URL"]
    pool = AsyncConnectionPool(url, min_size=1, max_size=8, open=False, kwargs={"autocommit": True, "row_factory": dict_row})
    await pool.open()
    async with pool.connection() as c:
        await c.execute(SCHEMA)


async def close():
    if pool:
        await pool.close()


def J(v):
    return Jsonb(v)


async def fetch(sql: str, *params) -> list[dict]:
    async with pool.connection() as c:
        cur = await c.execute(sql, params)
        return await cur.fetchall() if cur.description else []


async def one(sql: str, *params) -> dict | None:
    r = await fetch(sql, *params)
    return r[0] if r else None


async def run(sql: str, *params) -> None:
    async with pool.connection() as c:
        await c.execute(sql, params)
