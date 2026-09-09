"""4.1.1 adapter fidelity: keep provider evidence and requested filters."""

import asyncio
import json
from types import SimpleNamespace
from unittest import mock

import web_search_plus_mcp.providers as providers
import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server


def test_exa_snippet_prefers_highlights_over_leading_text():
    payload = {
        "results": [
            {
                "title": "Python docs",
                "url": "https://docs.python.org/3/library/functions.html",
                "text": "A" * 800 + " trailing boilerplate that is not the answer.",
                "highlights": [
                    "print() writes the given objects to the text stream.",
                    "flush is a keyword-only argument.",
                ],
                "score": 0.91,
            }
        ]
    }

    with mock.patch.object(providers, "make_request", return_value=payload):
        result = providers.search_exa("print flush", "exa-test-key")

    snippet = result["results"][0]["snippet"]
    assert "print() writes the given objects" in snippet
    assert "flush is a keyword-only argument" in snippet
    assert snippet[:20] != "A" * 20


def test_exa_snippet_falls_back_to_text_when_highlights_missing():
    payload = {
        "results": [
            {
                "title": "Example",
                "url": "https://example.com/page",
                "text": "Leading source sentence without highlights.",
                "highlights": [],
                "score": 0.4,
            }
        ]
    }

    with mock.patch.object(providers, "make_request", return_value=payload):
        result = providers.search_exa("example", "exa-test-key")

    assert result["results"][0]["snippet"] == "Leading source sentence without highlights."


def test_parallel_sends_max_results_and_source_policy_in_advanced_settings():
    fake_response = {
        "search_id": "search_411",
        "results": [
            {
                "title": "Parallel docs",
                "url": "https://docs.parallel.ai/search",
                "excerpts": [{"text": "Search API excerpt."}],
            }
        ],
    }

    with mock.patch.object(providers, "make_request", return_value=fake_response) as mock_request:
        providers.search_parallel(
            "Parallel AI Search API",
            "parallel-test-key",
            max_results=3,
            include_domains=["docs.parallel.ai"],
            exclude_domains=["example.com"],
        )

    _url, _headers, body = mock_request.call_args.args[:3]
    assert body["objective"] == "Parallel AI Search API"
    assert body["search_queries"] == ["Parallel AI Search API"]
    assert "site:" not in body["search_queries"][0]
    assert body["advanced_settings"]["max_results"] == 3
    assert body["advanced_settings"]["source_policy"] == {
        "include_domains": ["docs.parallel.ai"],
        "exclude_domains": ["example.com"],
    }


def test_tavily_search_sends_native_time_range():
    captured = {}

    def fake_request(_endpoint, _headers, body, *args, **kwargs):
        captured["body"] = body
        return {"results": []}

    with mock.patch.object(providers, "make_request", side_effect=fake_request):
        providers.search_tavily(
            "latest tavily changelog",
            "tvly-test",
            time_range="week",
        )

    assert captured["body"]["time_range"] == "week"
    assert captured["body"]["include_answer"] is False


def test_tavily_dispatch_applies_freshness():
    seen = {}

    def fake_tavily(**kwargs):
        seen.update(kwargs)
        return {
            "provider": "tavily",
            "query": kwargs["query"],
            "results": [{"url": "https://example.test/a", "title": "A", "snippet": "s"}],
            "images": [],
            "answer": "",
            "metadata": {},
        }

    with mock.patch.object(search, "provider_in_cooldown", lambda p: (False, 0)):
        with mock.patch.object(search, "cache_get", lambda **kw: None):
            with mock.patch.object(search, "cache_put", lambda **kw: None):
                with mock.patch.object(search, "reset_provider_health", lambda p: None):
                    with mock.patch.dict("os.environ", {"TAVILY_API_KEY": "tavily-test-key"}):
                        with mock.patch.object(search, "search_tavily", fake_tavily):
                            result = search.run_search_request(
                                query="latest tavily changelog",
                                provider="tavily",
                                freshness="week",
                            )

    assert seen["time_range"] == "week"
    assert result["metadata"]["freshness"] == {
        "requested": "week",
        "applied": True,
        "provider": "tavily",
        "native_value": "week",
    }


def _run_tavily_search(**kwargs):
    seen = {}

    def fake_tavily(**call):
        seen.update(call)
        return {
            "provider": "tavily",
            "query": call["query"],
            "results": [{"url": "https://example.test/a", "title": "A", "snippet": "s"}],
            "images": [],
            "answer": "",
            "metadata": {},
        }

    with mock.patch.object(search, "provider_in_cooldown", lambda p: (False, 0)):
        with mock.patch.object(search, "cache_get", lambda **kw: None):
            with mock.patch.object(search, "cache_put", lambda **kw: None):
                with mock.patch.object(search, "reset_provider_health", lambda p: None):
                    with mock.patch.dict("os.environ", {"TAVILY_API_KEY": "tavily-test-key"}):
                        with mock.patch.object(search, "search_tavily", fake_tavily):
                            result = search.run_search_request(
                                query="latest tavily changelog",
                                provider="tavily",
                                **kwargs,
                            )
    return seen, result


def test_tavily_time_range_wins_over_freshness_in_body_and_metadata():
    seen, result = _run_tavily_search(freshness="week", time_range="day")
    assert seen["time_range"] == "day"
    assert result["metadata"]["freshness"] == {
        "requested": "day",
        "applied": True,
        "provider": "tavily",
        "native_value": "day",
    }


def test_tavily_time_range_only_reports_applied_metadata():
    seen, result = _run_tavily_search(time_range="week")
    assert seen["time_range"] == "week"
    assert result["metadata"]["freshness"] == {
        "requested": "week",
        "applied": True,
        "provider": "tavily",
        "native_value": "week",
    }


def _tavily_v3_payload():
    return {
        "contract_version": "3.0",
        "request_id": "req_test",
        "execution_id": "exec_test",
        "capability": "search",
        "status": "ok",
        "results": [
            {
                "representative_observation_id": "obs_1",
                "observation_ids": ["obs_1"],
                "url": {
                    "observed": "https://example.com/a",
                    "canonical": "https://example.com/a",
                },
                "title": {"text": "Example title"},
                "snippet": {"text": "Provider-grounded snippet"},
                "text": None,
            }
        ],
        "observations": [],
        "policy_actions": [],
        "source_diversity": {
            "method": "provider_host_family_clusters",
            "method_version": "1",
            "method_degraded": False,
            "provider_count": 1,
            "host_count": 1,
            "source_family_count": 1,
            "unique_cluster_count": 1,
        },
        "provider_attempts": [
            {
                "attempt_id": "attempt-1",
                "provider": "tavily",
                "capability": "search",
                "outcome": "success",
                "retry_count": 0,
                "result_count": 1,
            }
        ],
        "routing_receipt": {
            "selected_provider": "tavily",
            "candidate_order": ["tavily"],
        },
        "cache_status": {"disposition": "miss"},
        "limits_applied": {},
        "stored_content": [],
        "dedup_clusters": [],
        "warnings": [],
        "error": None,
    }


def _call_web_search(monkeypatch, arguments):
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps(_tavily_v3_payload()), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = json.loads(asyncio.run(server.call_tool("web_search", arguments))[0].text)
    return seen, payload


def test_mcp_search_projects_tavily_freshness_metadata(monkeypatch):
    seen, payload = _call_web_search(
        monkeypatch,
        {"query": "latest tavily changelog", "provider": "tavily", "freshness": "week"},
    )
    assert "--freshness" in seen["cmd"]
    assert payload["metadata"]["freshness"] == {
        "requested": "week",
        "applied": True,
        "provider": "tavily",
        "native_value": "week",
    }


def test_mcp_search_time_range_only_projects_freshness_metadata(monkeypatch):
    seen, payload = _call_web_search(
        monkeypatch,
        {"query": "latest tavily changelog", "provider": "tavily", "time_range": "week"},
    )
    assert "--time-range" in seen["cmd"]
    assert payload["metadata"]["freshness"] == {
        "requested": "week",
        "applied": True,
        "provider": "tavily",
        "native_value": "week",
    }


def test_mcp_search_time_range_wins_projected_freshness_metadata(monkeypatch):
    seen, payload = _call_web_search(
        monkeypatch,
        {
            "query": "latest tavily changelog",
            "provider": "tavily",
            "freshness": "week",
            "time_range": "day",
        },
    )
    assert seen["cmd"][seen["cmd"].index("--time-range") + 1] == "day"
    assert payload["metadata"]["freshness"] == {
        "requested": "day",
        "applied": True,
        "provider": "tavily",
        "native_value": "day",
    }
