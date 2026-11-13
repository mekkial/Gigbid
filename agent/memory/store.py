"""Long-term memory on a LangGraph store (Postgres if reachable, else in-memory).
Namespaces: ("style", user) promoted style rules; ("outcome", user, category) promoted outcome stats;
("style_candidates", user) / ("outcome_raw", user, category) are counters feeding the promotion rules.
Raw tool output NEVER goes here."""
from __future__ import annotations

import os

from langgraph.store.memory import InMemoryStore


def make_store(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres"):
        try:
            import psycopg
            from langgraph.store.postgres import PostgresStore
            from psycopg.rows import dict_row

            conn = psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=3)
            st = PostgresStore(conn)
            st.setup()
            return st
        except Exception:  # noqa: BLE001 - degrade to in-memory for tests / no DB
            pass
    return InMemoryStore()


def list_items(store, namespace: tuple, limit: int = 200) -> list[dict]:
    return [{"key": i.key, **i.value} for i in store.search(namespace, limit=limit)]


def delete_item(store, namespace: tuple, key: str) -> None:
    store.delete(namespace, key)
