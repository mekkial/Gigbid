"""Durable async checkpointer: Postgres when DATABASE_URL is reachable (C6), SQLite file otherwise."""
from __future__ import annotations

import os


async def make_checkpointer(url: str | None = None, sqlite_path: str = ".local/checkpoints.sqlite"):
    url = os.environ.get("DATABASE_URL", "") if url is None else url
    if url.startswith("postgres"):
        try:
            import psycopg
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.rows import dict_row

            conn = await psycopg.AsyncConnection.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=3)
            cp = AsyncPostgresSaver(conn)
            await cp.setup()
            return cp
        except Exception:  # noqa: BLE001
            pass
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
    cp = AsyncSqliteSaver(await aiosqlite.connect(sqlite_path))
    await cp.setup()
    return cp
