"""Deterministic deadline/harvest races through the native research path."""

import math
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from types import SimpleNamespace

import pytest

from web_search_plus_mcp import config as config_module
from web_search_plus_mcp import http_client, providers, research, search
from web_search_plus_mcp.compat_v3 import legacy_request_to_v3
from web_search_plus_mcp.contract_v3 import Capability


@pytest.mark.parametrize("budget,finalization_seconds", [(2.0, 0.2), (20.0, 0.75)])
def test_research_harvest_keeps_partial_extract_after_provider_deadline(
    tmp_path, monkeypatch, budget, finalization_seconds,
):
    payload, calls, member_deadlines = _run_deadline_race(
        tmp_path, monkeypatch, budget, finalization_seconds,
    )
    assert calls[0]["max_wall_time_ms"] == int(budget * 1000)
    assert calls[0]["request_id"] == "harvest-regression:extract"
    assert member_deadlines and all(0 < left <= budget for left in member_deadlines)
    assert "extraction_error" not in payload["routing"]
    summaries = payload["source_summaries"]
    assert summaries[0]["content"] == "already fetched alpha evidence"
    assert [item["url"] for item in summaries] == [f"https://example.org/{i}" for i in range(3)]
    assert summaries[1]["error"] == "provider request timed out"
    assert summaries[2]["error"] == http_client.NOT_TRIED_DEADLINE_ERROR


def test_research_harvest_grace_still_bounds_stuck_extraction(tmp_path, monkeypatch):
    payload, calls, _deadlines = _run_deadline_race(tmp_path, monkeypatch, 2.0, 10.0)
    assert len(calls) == 1
    assert payload["source_summaries"] == []
    assert payload["routing"]["extraction_error"] == "timed out: research time budget exhausted"


def _run_deadline_race(tmp_path, monkeypatch, budget, finalization_seconds):
    # Start on a whole second just ahead of the real clock: parts of the
    # engine still read the real monotonic clock, and a fractional start can
    # round (start + 20.0) - start down to 19 999 ms.
    clock = SimpleNamespace(value=float(math.ceil(time.monotonic()) + 1))
    clock_module = SimpleNamespace(monotonic=lambda: clock.value)
    calls = []
    member_deadlines = []
    urls = [f"https://example.org/{i}" for i in range(3)]

    class TimedTask:
        """Run fake work synchronously, then enforce its simulated wait time."""
        def __init__(self, fn, *args):
            self.started = clock.value
            self.payload = fn(*args)
            self.elapsed = clock.value - self.started

        def add_done_callback(self, callback):
            callback(self)

        def done(self):
            return True

        def result(self, timeout=None):
            if timeout is not None and self.elapsed > timeout:
                # Match DaemonTask: concurrent.futures.TimeoutError is only an
                # alias of the builtin TimeoutError from Python 3.11 on.
                raise FuturesTimeoutError("daemon task did not finish in time")
            return self.payload

    def fake_search(**_kwargs):
        member_deadlines.append(http_client.remaining_seconds())
        return {
            "provider": "tavily", "query": "alpha evidence",
            "results": [{"url": url, "title": str(i), "snippet": "alpha"} for i, url in enumerate(urls)],
            "images": [], "metadata": {},
        }

    def fake_extract(**kwargs):
        calls.append(kwargs)
        # The adapter returns partial data at its deadline; projection/cleanup
        # still needs a little time before the daemon can publish the payload.
        clock.value += kwargs["max_wall_time_ms"] / 1000 + finalization_seconds
        return {
            "provider": "fixture-extract",
            "results": [
                {"url": urls[0], "content": "already fetched alpha evidence"},
                {"url": urls[1], "error": "provider request timed out"},
                {"url": urls[2], "error": http_client.NOT_TRIED_DEADLINE_ERROR},
            ],
        }

    monkeypatch.setattr(search, "time", SimpleNamespace(monotonic=lambda: clock.value, time=lambda: clock.value))
    monkeypatch.setattr(research, "time", clock_module)
    monkeypatch.setattr(http_client, "time", clock_module)
    monkeypatch.setattr(research, "DaemonTask", TimedTask)
    monkeypatch.setattr(providers, "search_tavily", fake_search)
    monkeypatch.setattr(search, "extract_plus", fake_extract)
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    config = config_module._deepcopy_default_config()
    config.update({
        "auto_routing": {"provider_priority": ["tavily"], "auto_allow": {"tavily": True}},
        "quality": {"filter_spam": False, "max_results_per_domain": 0},
        "routing": {"policy_mode": "classic"},
        "bounded_context": {"cache_root": str(tmp_path)},
        "v3": {"state_path": str(tmp_path / "state.sqlite3"), "cache_dir": str(tmp_path)},
    })
    request = legacy_request_to_v3(
        Capability.SEARCH,
        {"query": "alpha evidence", "provider": "tavily", "mode": "research",
         "research_time_budget": budget, "no_cache": True},
        request_id="harvest-regression",
    )
    execution = search.execute_v3_request(request, search._search_adapter(), config)
    return execution.legacy_payload, calls, member_deadlines
