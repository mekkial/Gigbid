"""The ONE marketplace interface (R1). Graph code depends only on this Protocol; adapters implement it.

Switch adapters with `marketplace.mode` in agent/config.yaml (gigsim | upwork_live).
"""
from __future__ import annotations

from typing import Any, Protocol


class MarketplaceUnavailable(Exception):
    """Raised after bounded retries fail; the graph/UI treat this as degraded mode."""


class MarketplacePort(Protocol):
    async def search_jobs(self, query: str, limit: int = 20) -> list[dict[str, Any]]: ...
    async def get_job(self, job_id: str) -> dict[str, Any]: ...
    async def get_client_history(self, client_id: str) -> dict[str, Any]: ...
    async def get_connects_balance(self) -> dict[str, Any]: ...
    async def list_messages(self, proposal_id: str) -> list[dict[str, Any]]: ...
    async def create_proposal_draft(self, payload: dict[str, Any], idempotency_key: str,
                                    dry_run: bool = False) -> dict[str, Any]: ...
    async def submit_proposal(self, proposal_id: str, idempotency_key: str) -> dict[str, Any]: ...
    async def send_message(self, proposal_id: str, text: str, idempotency_key: str) -> dict[str, Any]: ...


def get_marketplace(mode: str | None = None, **kw) -> MarketplacePort:
    """Factory: the only place that knows which adapter is active."""
    import yaml

    from agent.llm import CONFIG_PATH

    mode = mode or yaml.safe_load(CONFIG_PATH.read_text())["marketplace"]["mode"]
    if mode == "gigsim":
        from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
        return GigSimAdapter(**kw)
    if mode == "upwork_live":
        from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter
        return UpworkLiveAdapter(**kw)
    raise ValueError(f"unknown marketplace mode: {mode}")
