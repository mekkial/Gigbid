"""GigBid Marketplace MCP server (read + write) wrapping the marketplace port's adapters.

Run (HTTP, bearer auth):  python -m mcp_servers.marketplace.server
Writes carry: Pydantic-constrained inputs, declared output schema, annotations, a REQUIRED idempotency key,
a dry_run preview, a per-user rate limiter and an append-only audit log with the trace id.
"""
from __future__ import annotations

import os
from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from agent.marketplace_port import MarketplaceUnavailable, get_marketplace
from mcp_servers.common import BearerAuthMiddleware, Ledger, RateLimiter, identity

mcp = FastMCP("gigbid-marketplace", instructions="Marketplace read/write tools. Writes REQUIRE an idempotency_key; "
              "use dry_run=true to preview exactly what would be sent and what it costs before any real write.",
              host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MARKETPLACE_MCP_PORT", "8082")))
LEDGER = Ledger()
LIMITER = RateLimiter(int(os.environ.get("MCP_RATE_PER_MIN", "40")))
RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
WRITE_IDEM = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
WRITE_DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)
IdemKey = Annotated[str, Field(min_length=8, max_length=128, description="Unique per logical action; a retry with the same key never repeats the effect")]


def adapter_for(user: str):  # overridable in tests
    return get_marketplace(user=user)


class WriteResult(BaseModel):
    dry_run: bool = False
    replayed: bool = Field(default=False, description="true if this idempotency key was already applied")
    data: dict[str, Any]


async def _run(ctx: Context | None, tool: str, args: dict, fn, write: bool = False, idem: str | None = None, dry_run: bool = False):
    user, trace = identity(ctx)
    if not LIMITER.allow(user):
        raise ValueError("rate_limited: too many requests, retry shortly")
    if write and not dry_run:
        prev = LEDGER.get_idem(user, tool, idem)
        if prev is not None:
            LEDGER.audit(user, tool, args, {"replayed": True}, trace)
            return WriteResult(replayed=True, data=prev)
    try:
        res = await fn(adapter_for(user))
    except MarketplaceUnavailable as e:
        LEDGER.audit(user, tool, args, {"error": "marketplace_unavailable"}, trace)
        raise ValueError(f"marketplace_unavailable: {e}") from e
    LEDGER.audit(user, tool, args, res, trace)
    if write:
        if not dry_run:
            LEDGER.put_idem(user, tool, idem, res)
        return WriteResult(dry_run=dry_run, data=res)
    return res


@mcp.tool(annotations=RO, description="Search open jobs by keyword (title, description or skill). Returns up to `limit` jobs.")
async def search_jobs(query: Annotated[str, Field(max_length=200)] = "", limit: Annotated[int, Field(ge=1, le=50)] = 20,
                      ctx: Context = None) -> dict[str, Any]:
    return {"items": await _run(ctx, "search_jobs", {"query": query, "limit": limit}, lambda a: a.search_jobs(query, limit))}


@mcp.tool(annotations=RO, description="Get one job post by id.")
async def get_job(job_id: Annotated[str, Field(min_length=3, max_length=64)], ctx: Context = None) -> dict[str, Any]:
    return await _run(ctx, "get_job", {"job_id": job_id}, lambda a: a.get_job(job_id))


@mcp.tool(annotations=RO, description="Get a client's public history: spend, rating, hire rate, payment verification.")
async def get_client_history(client_id: Annotated[str, Field(min_length=3, max_length=64)], ctx: Context = None) -> dict[str, Any]:
    return await _run(ctx, "get_client_history", {"client_id": client_id}, lambda a: a.get_client_history(client_id))


@mcp.tool(annotations=RO, description="Get the user's current Connects balance.")
async def get_connects_balance(ctx: Context = None) -> dict[str, Any]:
    return await _run(ctx, "get_connects_balance", {}, lambda a: a.get_connects_balance())


@mcp.tool(annotations=RO, description="List messages in a proposal's conversation thread.")
async def list_messages(proposal_id: Annotated[str, Field(min_length=3, max_length=64)], ctx: Context = None) -> dict[str, Any]:
    return {"items": await _run(ctx, "list_messages", {"proposal_id": proposal_id}, lambda a: a.list_messages(proposal_id))}


@mcp.tool(annotations=RO, description="Market price statistics (p25/p50/p75, fixed and hourly USD) from real historical job postings "
          "for a category: ai_ml, fullstack or data_analyst.")
async def get_market_stats(category: Annotated[str, Field(min_length=2, max_length=40)], ctx: Context = None) -> dict[str, Any]:
    from agent.tools import market_stats
    user, trace = identity(ctx)
    res = market_stats(category)
    LEDGER.audit(user, "get_market_stats", {"category": category}, res, trace)
    return res


@mcp.tool(annotations=WRITE_IDEM, description="Create a proposal DRAFT (nothing is sent, no Connects spent). With dry_run=true returns "
          "exactly what would be created and its Connects cost.")
async def create_proposal_draft(job_id: Annotated[str, Field(min_length=3, max_length=64)],
                                cover_letter: Annotated[str, Field(min_length=150, max_length=3000)],
                                bid_amount: Annotated[float, Field(gt=0, le=100000)],
                                idempotency_key: IdemKey, dry_run: bool = False, ctx: Context = None) -> WriteResult:
    payload = {"job_id": job_id, "cover_letter": cover_letter, "bid_amount": bid_amount}
    return await _run(ctx, "create_proposal_draft", payload | {"idempotency_key": idempotency_key, "dry_run": dry_run},
                      lambda a: a.create_proposal_draft(payload, idempotency_key, dry_run), True, idempotency_key, dry_run)


@mcp.tool(annotations=WRITE_DESTRUCTIVE, description="SUBMIT a drafted proposal to the client. Spends Connects and cannot be undone. "
          "Only call after explicit human approval. dry_run=true previews the cost.")
async def submit_proposal(proposal_id: Annotated[str, Field(min_length=3, max_length=64)], idempotency_key: IdemKey,
                          dry_run: bool = False, ctx: Context = None) -> WriteResult:
    async def go(a):
        if dry_run:
            p = await a.get_proposal(proposal_id)
            bal = await a.get_connects_balance()
            return {"would_submit": proposal_id, "connects_cost": p["connects_cost"], "balance_after": bal["balance"] - p["connects_cost"]}
        return await a.submit_proposal(proposal_id, idempotency_key)
    return await _run(ctx, "submit_proposal", {"proposal_id": proposal_id, "idempotency_key": idempotency_key, "dry_run": dry_run},
                      go, True, idempotency_key, dry_run)


@mcp.tool(annotations=WRITE_DESTRUCTIVE, description="Send a message to the client in a proposal thread. Only after human approval.")
async def send_message(proposal_id: Annotated[str, Field(min_length=3, max_length=64)],
                       text: Annotated[str, Field(min_length=1, max_length=2000)], idempotency_key: IdemKey,
                       dry_run: bool = False, ctx: Context = None) -> WriteResult:
    async def go(a):
        if dry_run:
            return {"would_send": text, "to_thread": proposal_id}
        return await a.send_message(proposal_id, text, idempotency_key)
    return await _run(ctx, "send_message", {"proposal_id": proposal_id, "text": text, "idempotency_key": idempotency_key, "dry_run": dry_run},
                      go, True, idempotency_key, dry_run)


def http_app():
    """Streamable-HTTP ASGI app with bearer auth (A2)."""
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    mcp._session_manager = None          # each ASGI app gets its own session manager (it can only run once)
    app = mcp.streamable_http_app()
    app.router.routes.append(Route("/health", lambda r: JSONResponse({"status": "ok"})))
    return BearerAuthMiddleware(app)


def main():
    import uvicorn
    uvicorn.run(http_app(), host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MARKETPLACE_MCP_PORT", "8082")))


if __name__ == "__main__":
    main()
