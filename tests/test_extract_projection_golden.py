"""Golden cases for the extract projection: one outcome per requested URL.

Search dedups by canonical URL; extraction must not. Every case in
``fixtures/extract_projection/cases.json`` runs fixed provider answers through
the real engine and pins what the v3 response and the legacy payload report
for each requested URL (E1/E2, F06). The ``native`` rows in the fixture belong
to the Hermes native backend and are not used here.
"""

import json
import os
import socket
from pathlib import Path
from unittest import mock

import pytest

from web_search_plus_mcp import extract, providers
from web_search_plus_mcp.compat_v3 import legacy_request_to_v3, v3_response_to_legacy_extract
from web_search_plus_mcp.contract_v3 import Capability
from web_search_plus_mcp.extract_match import match_extract_items
from web_search_plus_mcp.orchestrator_v3 import execute_v3_request
from web_search_plus_mcp.runtime_v3 import (
    observations_from_legacy,
    project_extract_results_from_observations,
)

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "extract_projection" / "cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.fixture(autouse=True)
def _public_example_subdomains(monkeypatch):
    """IDN cases need hosts below example.org to resolve to a public address."""
    resolve = socket.getaddrinfo

    def fake(host, port, *args, **kwargs):
        if str(host).endswith((".example.org", ".example.com")):
            host = "93.184.216.34"
        return resolve(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def _env():
    return mock.patch.dict(
        os.environ, {"TAVILY_API_KEY": "tvly-test", "LINKUP_API_KEY": "linkup-test"}, clear=True
    )


def _provider_answer(name, rows):
    results = []
    for row in rows or []:
        item = {
            "url": row["url"],
            "title": "T",
            "content": row.get("content", ""),
            "raw_content": row.get("content", ""),
            "provider": name,
        }
        for key in ("error", "metadata"):
            if key in row:
                item[key] = row[key]
        results.append(item)
    return {"provider": name, "results": results}


class _Engine:
    """Fixed provider answers; records every batch handed to a provider."""

    def __init__(self, case):
        self.batches = {"tavily": [], "linkup": []}
        self.case = case

    def __enter__(self):
        def fake(name):
            def call(urls, *args, **kwargs):
                self.batches[name].append(list(urls))
                return _provider_answer(name, self.case.get(name))

            return call

        self._patches = [
            _env(),
            mock.patch.object(providers, "extract_tavily", side_effect=fake("tavily")),
            mock.patch.object(providers, "extract_linkup", side_effect=fake("linkup")),
        ]
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *exc):
        for patcher in reversed(self._patches):
            patcher.stop()


def _legacy_rows(payload):
    return [
        [item["url"], "error" if item.get("error") else "ok", None if item.get("error") else item.get("content")]
        for item in payload["results"]
    ]


def _v3_rows(response):
    rows = []
    for result in response.results:
        text = (result.get("text") or {}).get("text")
        rows.append([result["url"]["observed"], "ok" if text is not None else "error", text])
    return rows


def _execute(urls):
    request = legacy_request_to_v3(Capability.EXTRACT, {"urls": urls, "provider": "tavily"})
    return execute_v3_request(request, extract._extract_adapter(), extract.load_config())


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_v3_and_legacy_projection_match_golden(case):
    with _Engine(case) as engine:
        execution = _execute(case["urls"])
    legacy = v3_response_to_legacy_extract(execution)

    assert _v3_rows(execution.response) == case["v3"]
    assert _legacy_rows(legacy) == case["legacy"]
    assert len(execution.response.results) == len(case["urls"])
    # Each result is its own cluster and observation: nothing merged away.
    assert len({r["dedup_cluster_id"] for r in execution.response.results}) == len(case["urls"])
    assert len({r["result_id"] for r in execution.response.results}) == len(case["urls"])
    assert {name: len(batches) for name, batches in engine.batches.items()} == case["calls"]
    if "linkup_batch" in case:
        assert engine.batches["linkup"] == [case["linkup_batch"]]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_cached_replay_reports_the_same_statuses(case):
    with _Engine(case):
        first = extract.extract_plus(case["urls"], provider="tavily")
        second = extract.extract_plus(case["urls"], provider="tavily")

    assert _legacy_rows(first) == case["legacy"]
    # A replay (cache hit or fresh run) never changes cardinality or status.
    assert [row[1] for row in _legacy_rows(second)] == [row[1] for row in case["legacy"]]
    assert len(second["results"]) == len(case["urls"])


# -- leftover attribution ---------------------------------------------------


def test_unattributable_item_leaves_url_open_and_is_noted_not_cached():
    case = {
        "tavily": [
            {"url": "https://example.com/b", "content": "body b"},
            {"url": "https://cdn.example.org/a-final", "content": "unattributed"},
        ],
        "linkup": [],
    }
    # Two open URLs cannot be assigned a lone redirect by elimination.
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    with _Engine(case) as engine:
        first = extract.extract_plus(urls, provider="tavily")
        second = extract.extract_plus(urls, provider="tavily")

    assert _legacy_rows(first) == [
        ["https://example.com/a", "error", None],
        ["https://example.com/b", "ok", "body b"],
        ["https://example.com/c", "error", None],
    ]
    assert first["results"][0]["error"] == "No content could be extracted from this URL"
    assert "unattributed" not in json.dumps(first["results"])
    assert first["unmatched_results"] == [
        {"provider": "tavily", "url": "https://cdn.example.org/a-final", "has_content": True}
    ]
    # The partial answer is never replayed from cache as a complete one.
    assert not second.get("cached")
    assert len(engine.batches["tavily"]) == 2


def test_match_prefers_exact_then_canonical_then_reported_source_url():
    urls = ["https://example.com/a/", "https://example.com/b", "https://example.com/c"]
    items = [
        {"url": "https://cdn.example.org/c-final", "metadata": {"sourceURL": "https://example.com/c"}},
        {"url": "https://example.com/a"},
        {"url": "https://example.com/b"},
        {"url": "https://example.org/stray"},
    ]
    matched, unmatched = match_extract_items(urls, items)
    assert matched == [items[1], items[2], items[0]]
    assert unmatched == [items[3]]


def test_canonical_hit_is_ambiguous_for_two_spellings_but_exact_hit_decides():
    urls = ["https://example.com/p?ref=1", "https://example.com/p?ref=2"]
    ambiguous, left = match_extract_items(urls, [{"url": "https://example.com/p"}])
    assert ambiguous == [None, None] and len(left) == 1
    exact, _ = match_extract_items(urls, [{"url": urls[1]}])
    assert exact == [None, {"url": urls[1]}]


def test_empty_canonical_urls_are_not_merged_by_the_projection():
    items = [
        {"url": "/relative1", "content": "one"},
        {"url": "/relative2", "content": "two"},
    ]
    observations = observations_from_legacy(
        {"results": items}, "tavily", Capability.EXTRACT, "attempt-1"
    )
    assert {o["url"]["canonical"] for o in observations} == {""}
    results = project_extract_results_from_observations(observations)
    assert [r["url"]["observed"] for r in results] == ["/relative1", "/relative2"]
    assert [r["engine_rank"] for r in results] == [1, 2]
    assert len({r["dedup_cluster_id"] for r in results}) == 2
