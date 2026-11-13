"""GigSim: marketplace simulator (REST). Jobs, clients, Connects, proposals, messages, rate limits,
occasional 5xx, simulated clients with hidden preferences. Run: uvicorn gigsim.app:app --port 8081
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections import defaultdict, deque
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
RULES = yaml.safe_load((Path(__file__).parent / "rules.yaml").read_text())
TOKEN = __import__("os").environ.get("GIGSIM_API_TOKEN", "dev-token")

app = FastAPI(title="GigSim", version="1.0")

JOBS: dict[str, dict] = {}
CLIENTS: dict[str, dict] = {}
PROPOSALS: dict[str, dict] = {}
IDEMPOTENT: dict[str, dict] = {}
MESSAGES: dict[str, list[dict]] = defaultdict(list)
BALANCE: dict[str, int] = defaultdict(lambda: RULES["connects"]["starting_balance"])
HITS: dict[str, deque] = defaultdict(deque)
_rng = random.Random(RULES["reply_model"]["seed"])
FAIL_NEXT = {"n": 0}  # test hook: force the next n requests to 503


def _load():
    pool = ROOT / "data" / "processed" / "jobs_pool.jsonl"
    cl = ROOT / "data" / "processed" / "clients.json"
    if pool.exists():
        for line in pool.read_text().splitlines():
            j = json.loads(line)
            j.pop("gold", None)  # gold labels never exposed through the API
            JOBS[j["job_id"]] = j
    if cl.exists():
        for c in json.loads(cl.read_text()):
            CLIENTS[c["client_id"]] = c


_load()


def guard(request: Request, authorization: str = Header(default="")):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "bad token")
    user = request.headers.get("x-user", "anon")
    now = time.time()
    q = HITS[user]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RULES["rate_limit_per_minute"]:
        raise HTTPException(429, "rate limit", headers={"Retry-After": "5"})
    q.append(now)
    if FAIL_NEXT["n"] > 0:
        FAIL_NEXT["n"] -= 1
        raise HTTPException(503, "simulated outage")
    if _rng.random() < RULES["error_rate_5xx"]:
        raise HTTPException(503, "simulated transient error")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "jobs": len(JOBS)}


@app.post("/_admin/fail_next/{n}")
def fail_next(n: int):
    FAIL_NEXT["n"] = n
    return {"ok": True}


@app.get("/jobs")
def search_jobs(q: str = "", limit: int = 20, offset: int = 0, user: str = Depends(guard)):
    ql = q.lower()
    hits = [j for j in JOBS.values() if not ql or ql in j["title"].lower() or ql in j["description"].lower()
            or any(ql in s.lower() for s in j["required_skills"])]
    return {"total": len(hits), "items": hits[offset: offset + limit]}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: str = Depends(guard)):
    if job_id not in JOBS:
        raise HTTPException(404, "job not found")
    return JOBS[job_id]


@app.get("/clients/{client_id}")
def get_client(client_id: str, user: str = Depends(guard)):
    c = CLIENTS.get(client_id)
    if not c:
        raise HTTPException(404, "client not found")
    return {k: v for k, v in c.items() if k != "prefs"}  # hidden preferences never exposed


@app.get("/connects")
def connects(user: str = Depends(guard)):
    return {"balance": BALANCE[user]}


class ProposalIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1)
    bid_amount: float = Field(gt=0)
    boosted: bool = False


def _cost(job: dict, boosted: bool) -> int:
    c = RULES["connects"]
    cost = job["connects_cost"] if c["base_cost_from_job"] else 0
    return min(c["max_per_proposal"], cost + (c["surcharge_boosted"] if boosted else 0))


@app.post("/proposals")
def create_proposal(p: ProposalIn, idem: str = Header(alias="Idempotency-Key"), user: str = Depends(guard)):
    key = f"{user}:create:{idem}"
    if key in IDEMPOTENT:
        return IDEMPOTENT[key]
    job = JOBS.get(p.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    n = len(p.cover_letter)
    if n < RULES["proposal"]["min_chars"] or n > RULES["proposal"]["max_chars"]:
        raise HTTPException(422, f"cover letter must be {RULES['proposal']['min_chars']}-{RULES['proposal']['max_chars']} chars")
    pid = "prop-" + hashlib.sha1(key.encode()).hexdigest()[:10]
    PROPOSALS[pid] = {"proposal_id": pid, "user": user, "status": "draft", "connects_cost": _cost(job, p.boosted),
                      **p.model_dump()}
    IDEMPOTENT[key] = PROPOSALS[pid]
    return PROPOSALS[pid]


def _simulate_client(job: dict, prop: dict) -> str:
    """Hidden-preference client: decides ignore | reply | interview | hire. Deterministic per proposal."""
    cl = CLIENTS.get(job["client_id"], {})
    prefs = cl.get("prefs", {})
    rm = RULES["reply_model"]
    text = prop["cover_letter"].lower()
    words = set(re.findall(r"[a-z+#.]+", text))
    req = [s.lower() for s in job["required_skills"]]
    overlap = sum(1 for s in req if s in text or s in words) / max(1, len(req))
    score = rm["skill_overlap_weight"] * overlap
    ceiling = prefs.get("budget_ceiling", 1000)
    score += rm["budget_fit_weight"] * (1.0 if prop["bid_amount"] <= ceiling else 0.0)
    if re.search(r"dear sir|best candidate|apply for your job", text):
        score -= rm["generic_opening_penalty"] if prefs.get("dislikes_generic") else 0
    if re.search(r"\bi (recently )?(delivered|built|shipped)\b", text):
        score += 0.15
    r = random.Random(prop["proposal_id"]).random() * 0.5
    s = score + r
    return "hire" if s > 0.95 else "interview" if s > 0.8 else "reply" if s > 0.6 else "ignore"


@app.post("/proposals/{pid}/submit")
def submit_proposal(pid: str, idem: str = Header(alias="Idempotency-Key"), user: str = Depends(guard)):
    key = f"{user}:submit:{idem}"
    if key in IDEMPOTENT:
        return IDEMPOTENT[key]
    p = PROPOSALS.get(pid)
    if not p or p["user"] != user:
        raise HTTPException(404, "proposal not found")
    if p["status"] == "submitted":
        return p
    if BALANCE[user] < p["connects_cost"]:
        raise HTTPException(402, "insufficient connects")
    BALANCE[user] -= p["connects_cost"]
    p["status"] = "submitted"
    outcome = _simulate_client(JOBS[p["job_id"]], p)
    p["outcome"] = outcome
    if outcome != "ignore":
        txt = {"reply": "Thanks, can you tell me more about your approach?",
               "interview": "Looks promising. Are you free for a quick call this week?",
               "hire": "We'd like to hire you. What is your start date?"}[outcome]
        MESSAGES[pid].append({"from": "client", "text": txt, "ts": time.time()})
    IDEMPOTENT[key] = p
    return p


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.get("/proposals")
def list_proposals(user: str = Depends(guard)):
    return [p for p in PROPOSALS.values() if p["user"] == user]


@app.get("/proposals/{pid}/messages")
def list_messages(pid: str, user: str = Depends(guard)):
    return MESSAGES[pid]


@app.post("/proposals/{pid}/messages")
def send_message(pid: str, m: MessageIn, idem: str = Header(alias="Idempotency-Key"), user: str = Depends(guard)):
    key = f"{user}:msg:{pid}:{idem}"
    if key in IDEMPOTENT:
        return IDEMPOTENT[key]
    msg = {"from": "freelancer", "text": m.text, "ts": time.time()}
    MESSAGES[pid].append(msg)
    IDEMPOTENT[key] = msg
    return msg
