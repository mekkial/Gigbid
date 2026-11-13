"""Config-driven LLM access. Node -> tier -> provider/model all come from agent/config.yaml."""
from __future__ import annotations

import collections
import contextvars
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

import yaml
from openai import OpenAI

CONFIG_PATH = Path(__file__).with_name("config.yaml")
# per-call usage collector: a node wrapper sets a fresh list, chat() appends (model, in_tokens, out_tokens)
USAGE: contextvars.ContextVar[list | None] = contextvars.ContextVar("llm_usage", default=None)


def cost_usd(model: str, tin: int, tout: int) -> float:
    price = load_config()["models"].get("pricing_usd_per_mtok", {}).get(model, [0, 0])
    return (tin * price[0] + tout * price[1]) / 1e6


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


OVERRIDES: dict[str, str] = {}   # tier -> model id; set by evaluation runners to compare configurations (never in production)


def resolve(node: str, fallback: bool = False) -> dict:
    cfg = load_config()["models"]
    tier = "fallback" if fallback else cfg["nodes"][node]
    spec = dict(cfg["profiles"][cfg["profile"]][tier])
    if tier in OVERRIDES:
        spec["model"] = OVERRIDES[tier]
    prov = cfg["providers"][spec["provider"]]
    return {"model": spec["model"], "base_url": prov["base_url"], "key_env": prov["api_key_env"]}


class _Throttle:
    """Client-side tokens-per-minute limiter per model (sliding 60 s window). Threads block until there is room, so bursts from
    concurrent agents wait instead of triggering provider 429s."""

    def __init__(self):
        self.lock = threading.Lock()
        self.events: dict[str, collections.deque] = collections.defaultdict(collections.deque)   # model -> (ts, tokens)

    def acquire(self, model: str, est: int, limit: int):
        while True:
            with self.lock:
                now = time.time(); q = self.events[model]
                while q and now - q[0][0] > 60:
                    q.popleft()
                used = sum(t for _, t in q)
                if used + est <= limit or not q:
                    q.append((now, est)); return (now, est)
                wait = 60 - (now - q[0][0]) + 0.05
            time.sleep(max(0.05, min(wait, 5)))

    def wait_time(self, model: str, est: int, limit: int) -> float:
        """Non-blocking variant for async callers: 0 means 'go' (and the slot is reserved); otherwise seconds to wait."""
        with self.lock:
            now = time.time(); q = self.events[model]
            while q and now - q[0][0] > 60:
                q.popleft()
            if sum(t for _, t in q) + est <= limit or not q:
                q.append((now, est)); return 0.0
            return max(0.05, min(60 - (now - q[0][0]) + 0.05, 5))

    def settle(self, model: str, token, actual: int):
        with self.lock:
            q = self.events[model]
            for i, (ts, _) in enumerate(q):
                if ts == token[0]:
                    q[i] = (ts, actual); break


THROTTLE = _Throttle()


def chat(node: str, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.2) -> str:
    """One chat completion for a node; retries once on the fallback model."""
    last: Exception | None = None
    for fb in (False, True):
        r = resolve(node, fallback=fb)
        key = os.environ.get(r["key_env"], "")
        if not key:
            last = RuntimeError(f"missing env var {r['key_env']}")
            continue
        try:
            client = OpenAI(base_url=r["base_url"], api_key=key, timeout=90)
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            mc = load_config()["models"]
            tier = "fallback" if fb else mc["nodes"][node]
            effort = mc.get("reasoning_effort", {}).get(tier)
            if effort and r["model"].startswith("openai/gpt-oss"):
                kwargs["reasoning_effort"] = effort
            est = (len(system) + len(user)) // 3 + 700
            slot = THROTTLE.acquire(r["model"], est, mc.get("rate_limits", {}).get("tokens_per_minute", 7000))
            out = client.chat.completions.create(
                model=r["model"], temperature=temperature, **kwargs,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            if getattr(out, "usage", None):
                THROTTLE.settle(r["model"], slot, out.usage.total_tokens)
            u = USAGE.get()
            if u is not None and getattr(out, "usage", None):
                u.append((r["model"], out.usage.prompt_tokens, out.usage.completion_tokens))
            return out.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001 - fall through to fallback model
            last = e
    raise RuntimeError(f"LLM call failed for node {node}: {last}")


def chat_json(node: str, system: str, user: str, model_cls, retries: int = 2):
    """Chat in JSON mode and validate into a Pydantic model; re-asks with the validation error."""
    import json as _json
    from pydantic import ValidationError

    schema = _json.dumps(model_cls.model_json_schema())
    sys2 = f"{system}\n\nReturn ONLY a JSON object matching this JSON Schema:\n{schema}"
    msg, err = user, ""
    for _ in range(retries + 1):
        raw = chat(node, sys2, msg + (f"\n\nYour previous reply was invalid: {err}" if err else ""), json_mode=True)
        try:
            return model_cls.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            err = str(e)[:400]
    raise RuntimeError(f"{node}: could not get valid {model_cls.__name__}: {err}")
