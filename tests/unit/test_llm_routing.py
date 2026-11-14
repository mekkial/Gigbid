import os

import pytest

from agent import llm


@pytest.fixture(autouse=True)
def open_profile(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "open")


def test_node_routing_comes_from_config_and_fallbacks_are_a_different_model():
    for node in ("analyst", "writer", "critic", "client_liaison", "verifier"):
        primary, fb = llm.resolve(node), llm.resolve(node, fallback=True)
        assert primary["model"] != fb["model"], f"{node}: fallback must be a different model than its primary"
    assert llm.resolve("critic")["tier"] == "mid" and llm.resolve("critic", fallback=True)["tier"] == "strong"
    assert llm.resolve("analyst", fallback=True)["tier"] == "mid"


def test_local_profile_uses_ollama_without_a_key_or_rate_limit(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "local")
    r = llm.resolve("writer")
    assert r["provider"] == "ollama" and r["tpm"] is None and llm.api_key(r) == "ollama"


def test_every_node_has_a_tier_with_an_output_cap():
    cfg = llm.load_config()["models"]
    for node, tier in cfg["nodes"].items():
        assert tier in cfg["profiles"]["open"] and tier in cfg["max_output_tokens"], node
