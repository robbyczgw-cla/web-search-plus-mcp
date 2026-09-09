"""4.1.1 adapter fidelity: keep provider evidence and requested filters."""

import asyncio
import json
from datetime import datetime
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


def _run_exa_search(**kwargs):
    seen = {}
    real_exa = providers.search_exa

    def fake_exa(**call):
        seen.update(call)
        wire_response = {"results": [{"url": "https://example.test/a", "title": "A", "text": "s"}]}
        with mock.patch.object(providers, "make_request", return_value=wire_response) as http:
            result = real_exa(**call)
        body = http.call_args.args[2]
        assert result["metadata"]["applied_published_dates"] == {
            key: body[key] for key in ("startPublishedDate", "endPublishedDate") if key in body
        }
        return result

    with mock.patch.object(search, "provider_in_cooldown", lambda p: (False, 0)):
        with mock.patch.object(search, "cache_get", lambda **kw: None):
            with mock.patch.object(search, "cache_put", lambda **kw: None):
                with mock.patch.object(search, "reset_provider_health", lambda p: None):
                    with mock.patch.object(search, "validate_api_key", lambda prov, config=None: "exa-test-key"):
                        with mock.patch.dict("os.environ", {"EXA_API_KEY": "exa-test-key"}):
                            with mock.patch.object(search, "search_exa", fake_exa):
                                with mock.patch.object(providers, "search_exa", fake_exa):
                                    result = search.run_search_request(
                                        query="latest exa changelog",
                                        provider="exa",
                                        **kwargs,
                                    )
    return seen, result


def _exa_window_hours(native):
    start = datetime.fromisoformat(native["startPublishedDate"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(native["endPublishedDate"].replace("Z", "+00:00"))
    return (end - start).total_seconds() / 3600


def test_exa_time_range_wins_over_freshness_in_body_and_metadata():
    seen, result = _run_exa_search(freshness="week", time_range="day")
    assert seen["freshness"] == "day"
    meta = result["metadata"]["freshness"]
    assert meta["requested"] == "day"
    assert meta["applied"] is True
    assert meta["provider"] == "exa"
    assert 20 <= _exa_window_hours(meta["native_value"]) <= 28


def test_exa_time_range_only_applies_native_freshness():
    seen, result = _run_exa_search(time_range="week")
    assert seen["freshness"] == "week"
    meta = result["metadata"]["freshness"]
    assert meta["requested"] == "week"
    assert meta["applied"] is True
    assert meta["provider"] == "exa"
    assert 160 <= _exa_window_hours(meta["native_value"]) <= 176


def test_exa_time_range_hour_applies_one_hour_window():
    seen, result = _run_exa_search(time_range="hour")
    assert seen["freshness"] == "hour"
    assert not result.get("error")
    meta = result["metadata"]["freshness"]
    assert meta["requested"] == "hour"
    assert meta["applied"] is True
    assert 0.5 <= _exa_window_hours(meta["native_value"]) <= 1.5


def test_exa_search_returns_the_bounds_put_on_the_wire():
    captured = {}

    def fake_request(_url, _headers, body, timeout=30):
        captured["body"] = body
        return {"results": []}

    with mock.patch.object(providers, "make_request", fake_request):
        result = providers.search_exa("latest exa changelog", "exa-test-key", freshness="week")

    native = result["metadata"]["applied_published_dates"]
    assert captured["body"]["startPublishedDate"] == native["startPublishedDate"]
    assert captured["body"]["endPublishedDate"] == native["endPublishedDate"]


def test_exa_metadata_keeps_sent_bounds_when_clock_would_move():
    sent = {
        "startPublishedDate": "2026-01-01T00:00:00Z",
        "endPublishedDate": "2026-01-02T00:00:00Z",
    }

    def fake_exa(**call):
        return {
            "provider": "exa",
            "query": call["query"],
            "results": [{"url": "https://example.test/a", "title": "A", "snippet": "s"}],
            "images": [],
            "answer": "",
            "metadata": {"applied_published_dates": dict(sent)},
        }

    with mock.patch.object(search, "provider_in_cooldown", lambda p: (False, 0)):
        with mock.patch.object(search, "cache_get", lambda **kw: None):
            with mock.patch.object(search, "cache_put", lambda **kw: None):
                with mock.patch.object(search, "reset_provider_health", lambda p: None):
                    with mock.patch.object(search, "validate_api_key", lambda prov, config=None: "exa-test-key"):
                        with mock.patch.dict("os.environ", {"EXA_API_KEY": "exa-test-key"}):
                            with mock.patch.object(
                                providers,
                                "exa_date_bounds",
                                return_value=("2099-01-01T00:00:00Z", "2099-01-08T00:00:00Z"),
                            ):
                                with mock.patch.object(search, "search_exa", fake_exa):
                                    result = search.run_search_request(
                                        query="latest exa changelog",
                                        provider="exa",
                                        time_range="day",
                                    )

    assert result["metadata"]["freshness"]["native_value"] == sent
    assert "applied_published_dates" not in result["metadata"]


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


def test_mcp_search_keeps_exa_freshness_already_on_payload(monkeypatch):
    sent = {
        "requested": "week",
        "applied": True,
        "provider": "exa",
        "native_value": {
            "startPublishedDate": "2026-01-01T00:00:00Z",
            "endPublishedDate": "2026-01-08T00:00:00Z",
        },
    }
    v3 = _tavily_v3_payload()
    v3["routing_receipt"]["selected_provider"] = "exa"
    v3["provider_attempts"][0]["provider"] = "exa"
    v3["metadata"] = {"freshness": sent}

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=0, stdout=json.dumps(v3), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = json.loads(
        asyncio.run(
            server.call_tool(
                "web_search",
                {"query": "latest exa changelog", "provider": "exa", "time_range": "week"},
            )
        )[0].text
    )
    assert payload["metadata"]["freshness"] == sent


def test_mcp_search_uses_v3_warning_freshness_when_metadata_dropped(monkeypatch):
    sent = {
        "requested": "week",
        "applied": True,
        "provider": "exa",
        "native_value": {
            "startPublishedDate": "2026-01-01T00:00:00Z",
            "endPublishedDate": "2026-01-08T00:00:00Z",
        },
    }
    v3 = _tavily_v3_payload()
    v3["routing_receipt"]["selected_provider"] = "exa"
    v3["provider_attempts"][0]["provider"] = "exa"
    v3["warnings"] = [
        {
            "code": "wsp.freshness.applied",
            "message": "Native recency filter applied to the provider request.",
            "details": {"freshness": sent},
        }
    ]

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=0, stdout=json.dumps(v3), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = json.loads(
        asyncio.run(
            server.call_tool(
                "web_search",
                {"query": "latest exa changelog", "provider": "exa", "time_range": "week"},
            )
        )[0].text
    )
    assert payload["metadata"]["freshness"] == sent
