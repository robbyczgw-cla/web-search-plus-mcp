from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from web_search_plus_mcp import extract, search, server
from web_search_plus_mcp.http_client import ProviderRequestError
from web_search_plus_mcp.provider_registry import PROVIDER_ENV_KEYS


def _server_subprocess_runtime_config(tmp_path: Path, monkeypatch) -> dict:
    """Build the config loaded by search.py when server.py spawns it."""
    for env_name in PROVIDER_ENV_KEYS:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.delenv("KEENABLE_ALLOW_PUBLIC", raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "brave-test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("LINKUP_API_KEY", "linkup-test-key")
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(tmp_path / "missing.json"))
    return search.load_config()


def _routing(provider: str = "brave") -> dict:
    return {
        "provider": provider,
        "confidence": 0.9,
        "confidence_level": "high",
        "reason": "issue 27 regression fixture",
        "routing_policy": "routing-v2",
        "top_signals": [],
        "scores": {provider: 1.0},
        "auto_allow_excluded": [],
        "analysis_summary": {"routing_class": "general"},
    }


@pytest.mark.parametrize(
    ("tool_name", "arguments", "runner_name", "planner"),
    [
        (
            "web_search",
            {"query": "fallback test", "provider": "auto"},
            "run_search_request_v3",
            search._plan_search_v3,
        ),
        (
            "web_extract",
            {"urls": ["https://example.com"], "provider": "auto"},
            "run_extract_request_v3",
            extract._plan_extract_v3,
        ),
    ],
)
def test_server_auto_requests_build_multi_candidate_plans(
    tmp_path,
    monkeypatch,
    capsys,
    tool_name,
    arguments,
    runner_name,
    planner,
):
    config = _server_subprocess_runtime_config(tmp_path, monkeypatch)
    plans = []
    commands = []

    class StubResponse:
        def to_dict(self):
            return {"contract_version": "3.0", "status": "ok", "results": []}

    def capture_plan(request, *, config):
        plans.append(planner(request, config))
        return StubResponse()

    async def capture_command(cmd, **_kwargs):
        commands.append(cmd)
        return []

    monkeypatch.setattr(server, "_run_cmd", capture_command)
    asyncio.run(server.call_tool(tool_name, arguments))
    assert len(commands) == 1

    monkeypatch.setattr(search, "load_config", lambda: config)
    monkeypatch.setattr(search, "auto_route_provider", lambda _query, _config: _routing())
    monkeypatch.setattr(search, runner_name, capture_plan)
    monkeypatch.setattr(sys, "argv", commands[0][1:])

    search.main()

    capsys.readouterr()
    assert len(plans) == 1
    assert len(plans[0].candidate_order) > 1


def test_search_falls_back_after_first_provider_quota_error(tmp_path, monkeypatch):
    config = _server_subprocess_runtime_config(tmp_path, monkeypatch)
    config["v3"] = {
        "state_path": str(tmp_path / "state.sqlite3"),
        "cache_dir": str(tmp_path),
        "default_max_provider_attempts": 3,
        "max_attempts_per_provider": 1,
    }
    calls = []

    def brave_quota(**_kwargs):
        calls.append("brave")
        raise ProviderRequestError(
            "Brave quota exhausted", status_code=429, transient=True
        )

    def tavily_success(**_kwargs):
        calls.append("tavily")
        return {
            "provider": "tavily",
            "query": "fallback test",
            "results": [
                {
                    "title": "Fallback result",
                    "url": "https://example.com/result",
                    "snippet": "served by the second provider",
                }
            ],
            "images": [],
            "answer": "",
            "metadata": {},
        }

    monkeypatch.setattr(search, "auto_route_provider", lambda _query, _config: _routing())
    monkeypatch.setattr(search, "search_brave", brave_quota)
    monkeypatch.setattr(search, "search_tavily", tavily_success)
    monkeypatch.setattr(search, "load_config", lambda: config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(server.SEARCH_SCRIPT),
            "--query",
            "fallback test",
            "--provider",
            "auto",
            "--compact",
            "--contract-v3",
            "--no-cache",
        ],
    )

    captured = []
    real_runner = search.run_search_request_v3

    def capture_response(request, *, config):
        response = real_runner(request, config=config)
        captured.append(response)
        return response

    monkeypatch.setattr(search, "run_search_request_v3", capture_response)
    search.main()

    assert calls == ["brave", "tavily"]
    assert captured[0].routing_receipt["candidate_order"][:2] == [
        "brave",
        "tavily",
    ]
    assert captured[0].routing_receipt["selected_provider"] == "tavily"
    assert [attempt.provider for attempt in captured[0].provider_attempts[:2]] == [
        "brave",
        "tavily",
    ]


def test_extract_falls_back_after_first_provider_quota_error(tmp_path, monkeypatch):
    config = _server_subprocess_runtime_config(tmp_path, monkeypatch)
    config["v3"] = {
        "state_path": str(tmp_path / "state.sqlite3"),
        "cache_dir": str(tmp_path),
        "default_max_provider_attempts": 3,
        "max_attempts_per_provider": 1,
    }
    calls = []

    def tavily_quota(*_args, **_kwargs):
        calls.append("tavily")
        raise ProviderRequestError(
            "Tavily quota exhausted", status_code=429, transient=True
        )

    def linkup_success(*_args, **_kwargs):
        calls.append("linkup")
        return {
            "provider": "linkup",
            "results": [
                {
                    "url": "https://example.com",
                    "content": "served by the second provider",
                }
            ],
        }

    monkeypatch.setattr(search, "extract_tavily", tavily_quota)
    monkeypatch.setattr(search, "extract_linkup", linkup_success)
    monkeypatch.setattr(
        extract,
        "_validate_extract_urls",
        lambda urls, _config: list(urls),
    )
    monkeypatch.setattr(search, "load_config", lambda: config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(server.SEARCH_SCRIPT),
            "--extract-urls",
            "https://example.com",
            "--provider",
            "auto",
            "--compact",
            "--contract-v3",
            "--no-cache",
        ],
    )

    captured = []
    real_runner = search.run_extract_request_v3

    def capture_response(request, *, config):
        response = real_runner(request, config=config)
        captured.append(response)
        return response

    monkeypatch.setattr(search, "run_extract_request_v3", capture_response)
    search.main()

    assert calls == ["tavily", "linkup"]
    assert captured[0].routing_receipt["candidate_order"][:2] == [
        "tavily",
        "linkup",
    ]
    assert captured[0].routing_receipt["selected_provider"] == "linkup"
    assert [attempt.provider for attempt in captured[0].provider_attempts[:2]] == [
        "tavily",
        "linkup",
    ]
