"""No provider HTTP request starts after the request deadline (5.1.1, review #3).

The attempt engine binds the request deadline for each provider operation.
Batch adapters check it before every per-URL request, adapters with their own
transport apply it like the shared HTTP client, and Research hands its
remaining deadline to the source extraction.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from unittest import mock
from urllib.error import URLError

import pytest

from web_search_plus_mcp import config as config_module
from web_search_plus_mcp import extract, http_client, provider_registry, providers, search
from web_search_plus_mcp.compat_v3 import legacy_request_to_v3
from web_search_plus_mcp.contract_v3 import Capability
from web_search_plus_mcp.daemon_tasks import DaemonTask
from web_search_plus_mcp.errors_v3 import classify_provider_error
from web_search_plus_mcp.http_client import (
    NOT_TRIED_DEADLINE_ERROR,
    RequestDeadlineExceeded,
    request_deadline_scope,
    request_timeout_cap,
)

PAGE = {"success": True, "data": {"markdown": "page body", "metadata": {}}}


@pytest.fixture
def public_dns(monkeypatch):
    def fake(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def _isolated_config(tmp_path: Path) -> dict:
    cfg = config_module._deepcopy_default_config()
    cfg["v3"] = {
        "cache_dir": str(tmp_path),
        "state_path": str(tmp_path / "state.sqlite3"),
        "operator_receipt_journal": False,
    }
    cfg["bounded_context"] = {"cache_root": str(tmp_path)}
    return cfg


# --- shared HTTP client ------------------------------------------------------


def test_shared_client_refuses_to_start_a_request_after_the_deadline():
    with mock.patch.object(http_client, "_safe_opener") as opener, \
         mock.patch.object(http_client, "_pooled_open") as pooled:
        with request_deadline_scope(time.monotonic() - 0.001):
            with pytest.raises(RequestDeadlineExceeded) as caught:
                http_client.make_request("https://api.example/", {}, {"q": 1})
            with pytest.raises(RequestDeadlineExceeded):
                http_client.make_get_request("https://api.example/", {})
    opener.assert_not_called()
    pooled.assert_not_called()
    assert str(caught.value) == NOT_TRIED_DEADLINE_ERROR
    assert classify_provider_error(caught.value, provider="exa").error_class.value == "timeout"


def test_socket_timeout_shrinks_to_the_time_left():
    with request_deadline_scope(time.monotonic() + 2.0):
        assert 1.0 < http_client.dispatch_timeout(30) <= 2.0
        with request_timeout_cap(0.5):
            assert http_client.dispatch_timeout(30) == 0.5
        # A nested scope only tightens the deadline.
        with request_deadline_scope(time.monotonic() + 60):
            assert http_client.remaining_seconds() <= 2.0
    assert http_client.remaining_seconds() is None
    assert http_client.dispatch_timeout(30) == 30


# --- batch extraction --------------------------------------------------------


def test_firecrawl_batch_starts_no_request_after_the_deadline(tmp_path, public_dns):
    """Astra F02: small budget, three URLs, a first page slower than the budget."""
    starts = []
    first = threading.Event()

    def slow_http(endpoint, headers, body, **kwargs):
        starts.append(time.monotonic())
        first.set()
        time.sleep(0.4)
        return PAGE

    urls = [f"https://deadline-fc.example/{name}" for name in "abc"]
    with mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}), \
         mock.patch.object(providers, "make_request", slow_http):
        task = DaemonTask(
            extract.extract_plus, urls, provider="firecrawl",
            config=_isolated_config(tmp_path), max_wall_time_ms=250,
        )
        assert first.wait(3)
        result = task.result(5)

    assert len(starts) == 1
    by_url = {item["url"]: item for item in result["results"]}
    assert by_url[urls[0]]["content"] == "page body"
    for url in urls[1:]:
        assert by_url[url]["error"] == NOT_TRIED_DEADLINE_ERROR


@pytest.mark.parametrize("provider", ["firecrawl", "serper", "keenable"])
def test_sequential_batches_keep_fetched_pages_and_skip_the_rest(provider):
    calls = []

    def slow(*args, **kwargs):
        calls.append(args[0])
        time.sleep(0.05)
        return {"success": True, "data": {"markdown": "body"}, "markdown": "body", "content": "body"}

    urls = [f"https://batch.example/{i}" for i in range(3)]
    adapter = getattr(providers, f"extract_{provider}")
    with mock.patch.object(providers, "make_request", slow), \
         mock.patch.object(providers, "make_get_request", slow), \
         request_deadline_scope(time.monotonic() + 0.02):
        result = adapter(urls, "test-key")

    assert len(calls) == 1
    assert result["results"][0]["content"] == "body"
    assert [item.get("error") for item in result["results"][1:]] == [NOT_TRIED_DEADLINE_ERROR] * 2


def test_linkup_queued_fetches_see_the_deadline_on_their_worker_threads():
    calls = []
    lock = threading.Lock()

    def slow(endpoint, headers, body, **kwargs):
        with lock:
            calls.append(body["url"])
        time.sleep(0.4)
        return {"markdown": "body"}

    urls = [f"https://linkup-batch.example/{i}" for i in range(7)]
    with mock.patch.object(providers, "make_request", slow), \
         request_deadline_scope(time.monotonic() + 0.2):
        result = providers.extract_linkup(urls, "linkup-test")

    # Five workers start at once; the two queued fetches would begin after the deadline.
    assert len(calls) == 5
    errors = [item.get("error") for item in result["results"]]
    assert errors.count(NOT_TRIED_DEADLINE_ERROR) == 2
    assert sum(item.get("content") == "body" for item in result["results"]) == 5


# --- providers with their own transport --------------------------------------


@pytest.mark.parametrize(
    "provider, payload",
    [("octen", {"query": "q"}), ("tinyfish", {"query": "q"})],
)
def test_own_transports_honour_the_attempt_cap_and_deadline(provider, payload):
    module_globals = provider_registry.PROVIDER_SPECS[provider].execute_search.__globals__
    seen = []

    def fake_open(request, timeout):
        seen.append(timeout)
        raise URLError("fixture")

    with mock.patch.dict(module_globals, {"_open_request": fake_open}):
        with request_timeout_cap(10.0):
            with pytest.raises(http_client.ProviderRequestError):
                module_globals["_request"](payload, "key", 120)
        with request_deadline_scope(time.monotonic() - 0.001):
            with pytest.raises(RequestDeadlineExceeded):
                module_globals["_request"](payload, "key", 120)

    assert seen == [10.0]


def test_donsetch_extract_caps_the_session_and_skips_urls_after_the_deadline():
    module_globals = provider_registry.PROVIDER_SPECS["donsetch"].execute_extract.__globals__
    sessions = []

    class FakeSession:
        def __init__(self, binary, timeout_seconds):
            self.timeout_seconds = timeout_seconds
            self.calls = []
            sessions.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def call(self, tool, arguments):
            self.calls.append(arguments["url"])
            time.sleep(0.05)
            return {}

    def project(payload, url):
        return {"url": url, "content": "body"}

    urls = [f"https://donsetch.example/{i}" for i in range(3)]
    with mock.patch.dict(module_globals, {
        "DonsetchSession": FakeSession,
        "_resolve_binary": lambda key, config: "/bin/donsetch",
        "_project_fetch_item": project,
    }), request_timeout_cap(10.0), request_deadline_scope(time.monotonic() + 0.02):
        result = module_globals["execute_extract"](
            None, "donsetch", urls, None, "markdown", False, False, False, {}, False,
        )

    assert sessions[0].timeout_seconds <= 0.02
    assert sessions[0].calls == urls[:1]
    assert [item.get("error") for item in result["results"]] == [None] + [NOT_TRIED_DEADLINE_ERROR] * 2


# --- Research ---------------------------------------------------------------


def test_research_members_and_extraction_get_the_research_deadline(tmp_path, monkeypatch):
    member_deadlines = []
    extract_calls = []

    def fake_search(**_kwargs):
        member_deadlines.append(http_client.remaining_seconds())
        return {
            "provider": "tavily",
            "query": "compare alpha beta",
            "results": [{"title": "t", "url": "https://research.example/a", "snippet": "s"}],
            "images": [],
            "metadata": {},
        }

    def fake_extract(**kwargs):
        extract_calls.append(kwargs)
        return {"provider": "fixture-extract", "results": []}

    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setattr(providers, "search_tavily", fake_search)
    monkeypatch.setattr(search, "extract_plus", fake_extract)
    cfg = _isolated_config(tmp_path)
    cfg["auto_routing"]["provider_priority"] = ["tavily"]
    cfg["auto_routing"]["auto_allow"] = {"tavily": True}
    cfg["tavily"] = {}
    request = legacy_request_to_v3(
        Capability.SEARCH,
        {
            "query": "compare alpha beta",
            "provider": "tavily",
            "mode": "research",
            "research_time_budget": 5.0,
            "no_cache": True,
        },
        request_id="research-deadline",
    )

    search.execute_v3_request(request, search._search_adapter(), cfg)

    assert member_deadlines and all(0 < left <= 5.0 for left in member_deadlines)
    assert len(extract_calls) == 1
    assert 0 < extract_calls[0]["max_wall_time_ms"] <= 5000
    assert extract_calls[0]["request_id"] == "research-deadline:extract"
