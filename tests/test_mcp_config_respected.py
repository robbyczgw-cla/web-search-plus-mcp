"""A tool call must run with the config the engine accepts, and never move it.

5.1.4: the server's own validator rejected `extract_provider_priority: []` (the
engine reads it as "default order"), renamed config.json to .broken-* while
resolving `detail`, and the search then ran without the user's disabled providers.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from web_search_plus_mcp import search, server

pytestmark = pytest.mark.inprocess


def test_tool_call_keeps_config_and_disabled_provider(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "auto_routing": {"extract_provider_priority": [], "disabled_providers": ["brave"]},
    }))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(config_path))
    monkeypatch.delenv(server.DETAIL_ENV_VAR, raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "brave-test-key-long-enough")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key-long-enough")
    calls = []

    def fake(name):
        def run(**kwargs):
            calls.append(name)
            return {"provider": name, "query": kwargs.get("query"),
                    "results": [{"title": "T", "url": f"https://{name}.example/page", "snippet": "s"}]}
        return run

    monkeypatch.setattr(search._providers, "search_brave", fake("brave"))
    monkeypatch.setattr(search._providers, "search_tavily", fake("tavily"))

    text = asyncio.run(server.call_tool("web_search", {"query": "python release notes", "provider": "auto"}))[0].text

    assert config_path.exists(), "a tool call must not move the user's config"
    assert not list(tmp_path.glob("config.json.broken-*"))
    assert "brave" not in calls, "disabled provider was used"
    assert "brave.example" not in text
