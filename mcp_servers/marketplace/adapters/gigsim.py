"""GigSim adapter: bounded retries with backoff on 429/5xx, dry_run preview, idempotency keys."""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from agent.marketplace_port import MarketplaceUnavailable


class GigSimAdapter:
    def __init__(self, base_url: str | None = None, token: str | None = None, user: str = "demo",
                 client: httpx.AsyncClient | None = None, retries: int = 3, backoff: float = 0.4):
        self.base_url = base_url or os.environ.get("GIGSIM_BASE_URL", "http://localhost:8081")
        self.headers = {"Authorization": f"Bearer {token or os.environ.get('GIGSIM_API_TOKEN', 'dev-token')}",
                        "x-user": user}
        self._client = client
        self.retries, self.backoff = retries, backoff

    async def _req(self, method: str, path: str, **kw) -> Any:
        headers = {**self.headers, **kw.pop("headers", {})}
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                if self._client is not None:
                    r = await self._client.request(method, path, headers=headers, **kw)
                else:
                    async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as c:
                        r = await c.request(method, path, headers=headers, **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    last = RuntimeError(f"{r.status_code} from GigSim")
                    await asyncio.sleep(self.backoff * (2 ** attempt))
                    continue
                if r.status_code >= 400:
                    raise ValueError(f"GigSim {r.status_code}: {r.text}")
                return r.json()
            except httpx.TransportError as e:
                last = e
                await asyncio.sleep(self.backoff * (2 ** attempt))
        raise MarketplaceUnavailable(str(last))

    async def search_jobs(self, query: str, limit: int = 20):
        return (await self._req("GET", "/jobs", params={"q": query, "limit": limit}))["items"]

    async def get_job(self, job_id: str):
        return await self._req("GET", f"/jobs/{job_id}")

    async def get_client_history(self, client_id: str):
        return await self._req("GET", f"/clients/{client_id}")

    async def get_connects_balance(self):
        return await self._req("GET", "/connects")

    async def list_messages(self, proposal_id: str):
        return await self._req("GET", f"/proposals/{proposal_id}/messages")

    async def create_proposal_draft(self, payload, idempotency_key, dry_run=False):
        if dry_run:  # exact preview + cost, nothing sent
            job = await self.get_job(payload["job_id"])
            bal = await self.get_connects_balance()
            return {"dry_run": True, "would_send": payload, "connects_cost": job["connects_cost"],
                    "balance_after": bal["balance"] - job["connects_cost"]}
        return await self._req("POST", "/proposals", json=payload, headers={"Idempotency-Key": idempotency_key})

    async def submit_proposal(self, proposal_id, idempotency_key):
        return await self._req("POST", f"/proposals/{proposal_id}/submit", headers={"Idempotency-Key": idempotency_key})

    async def send_message(self, proposal_id, text, idempotency_key):
        return await self._req("POST", f"/proposals/{proposal_id}/messages", json={"text": text},
                               headers={"Idempotency-Key": idempotency_key})
