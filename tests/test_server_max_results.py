"""web_search honours defaults.max_results when the client omits count."""
from __future__ import annotations

import asyncio

import pytest

from web_search_plus_mcp import server


def _command(monkeypatch, arguments):
    commands = []

    async def capture(cmd, **_kwargs):
        commands.append(cmd)
        return []

    monkeypatch.setattr(server, "_run_cmd", capture)
    asyncio.run(server.call_tool("web_search", arguments))
    assert len(commands) == 1
    return commands[0]


def _max_results(cmd):
    if "--max-results" not in cmd:
        return None
    return cmd[cmd.index("--max-results") + 1]


def test_omitted_count_leaves_max_results_to_config(monkeypatch):
    # search.py then falls back to defaults.max_results from config.json.
    assert _max_results(_command(monkeypatch, {"query": "q", "provider": "serper"})) is None


@pytest.mark.parametrize("count", [1, 3, 20])
def test_explicit_count_is_forwarded(monkeypatch, count):
    cmd = _command(monkeypatch, {"query": "q", "provider": "serper", "count": count})
    assert _max_results(cmd) == str(count)


def test_null_count_behaves_like_omitted(monkeypatch):
    cmd = _command(monkeypatch, {"query": "q", "provider": "serper", "count": None})
    assert _max_results(cmd) is None
