"""Config-driven LLM access. Node -> tier -> provider/model all come from agent/config.yaml."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from openai import OpenAI

CONFIG_PATH = Path(__file__).with_name("config.yaml")


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def resolve(node: str, fallback: bool = False) -> dict:
    cfg = load_config()["models"]
    tier = "fallback" if fallback else cfg["nodes"][node]
    spec = cfg["profiles"][cfg["profile"]][tier]
    prov = cfg["providers"][spec["provider"]]
    return {"model": spec["model"], "base_url": prov["base_url"], "key_env": prov["api_key_env"]}


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
            client = OpenAI(base_url=r["base_url"], api_key=key, timeout=60)
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            out = client.chat.completions.create(
                model=r["model"], temperature=temperature, **kwargs,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            return out.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001 - fall through to fallback model
            last = e
    raise RuntimeError(f"LLM call failed for node {node}: {last}")
