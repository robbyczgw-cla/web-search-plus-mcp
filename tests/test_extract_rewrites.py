"""Redirect/encoding rewrites must not discard already-paid extraction content."""
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from web_search_plus_mcp import extract, providers
from web_search_plus_mcp.extract_match import match_extract_items


@pytest.mark.parametrize("requested,rewritten", [
    ("http://example.org/a", "https://example.org/a"),
    ("https://example.org/Köln", "https://example.org/K%C3%B6ln"),
    ("https://example.org/a%2fb", "https://example.org/a%2Fb"),
])
def test_rewritten_url_content_is_preserved_in_batch(monkeypatch, requested, rewritten):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    other = "https://example.org/other"
    rows = [{"url": rewritten, "content": "paid"}, {"url": other, "content": "other"}]
    monkeypatch.setattr(providers, "extract_tavily", lambda *a, **kw: {"provider": "tavily", "results": rows})
    result = extract.extract_plus([requested, other], provider="tavily")
    assert not result.get("error")
    assert [r["content"] for r in result["results"]] == ["paid", "other"]


def test_rewrite_key_matches_multiple_reordered_pages_without_singleton_rescue():
    urls = ["http://example.org/a", "https://example.org/Köln", "https://example.org/a%2fb"]
    rows = [{"url": url} for url in [
        "https://example.org/a%2Fb", "https://example.org/a", "https://example.org/K%C3%B6ln",
    ]]
    assert match_extract_items(urls, rows) == ([rows[1], rows[2], rows[0]], [])


def test_single_remaining_redirect_is_matched_but_batches_are_not_positional():
    urls = ["https://example.org/a", "https://example.org/b"]
    rows = [{"url": "https://example.com/new-b", "content": "b"}, {"url": urls[0], "content": "a"}]
    matched, unmatched = match_extract_items(urls, rows)
    assert matched == [rows[1], rows[0]] and unmatched == []
    rows[1]["url"] = "https://example.com/new-a"
    assert match_extract_items(urls, rows) == ([None, None], rows)


def test_weak_matching_preserves_ref_ambiguity():
    urls = ["http://example.org/a?ref=1", "http://example.org/a?ref=2"]
    rows = [{"url": "https://example.org/a", "content": "ambiguous"}]
    assert match_extract_items(urls, rows) == ([None, None], rows)
    rows.insert(0, {"url": urls[0], "content": "exact"})
    assert match_extract_items(urls, rows) == ([rows[0], None], [rows[1]])


@pytest.mark.parametrize("provider", ["keenable", "serper", "linkup", "firecrawl"])
@pytest.mark.parametrize("failure", [False, True])
def test_urlwise_adapters_stamp_requested_url(monkeypatch, provider, failure):
    urls = ["https://example.org/a", "https://example.org/b"]
    def answer(*args, **kwargs):
        if failure:
            raise providers.ProviderRequestError("offline", transient=False)
        return {"url": "https://example.com/redirected", "content": "paid", "markdown": "paid",
                "data": {"markdown": "paid", "metadata": {"url": "https://example.com/redirected"}}}
    monkeypatch.setattr(providers, "make_request", answer)
    monkeypatch.setattr(providers, "make_get_request", answer)
    if failure and provider in {"firecrawl", "linkup"}:
        # Preserve the adapters' existing all-URLs-failed exception contract.
        calls = 0
        def partial(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise providers.ProviderRequestError("offline", transient=False)
            return {"markdown": "paid", "data": {"markdown": "paid"}}
        monkeypatch.setattr(providers, "make_request", partial)
    result = getattr(providers, f"extract_{provider}")(urls, "test-key")
    assert [r.get("requested_url") for r in result["results"]] == urls


def test_keenable_cross_host_redirect_api_retains_each_page(monkeypatch):
    monkeypatch.setenv("KEENABLE_API_KEY", "test-key")
    urls = ["https://example.org/a", "https://example.org/b"]
    def answer(endpoint, *args, **kwargs):
        requested = parse_qs(urlsplit(endpoint).query)["url"][0]
        page = requested.rsplit("/", 1)[-1]
        return {"url": f"https://example.com/redirect-{page}", "content": f"paid {page}"}
    monkeypatch.setattr(providers, "make_get_request", answer)
    result = extract.extract_plus(urls, provider="keenable")
    assert not result.get("error")
    assert [r["content"] for r in result["results"]] == ["paid a", "paid b"]


def test_only_unmatched_results_are_a_diagnostic_provider_failure(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(providers, "extract_tavily", Mock(return_value={
        "provider": "tavily", "results": [{"url": "https://example.org/stray", "content": "stray"}],
    }))
    result = extract.extract_plus(["https://example.org/a", "https://example.org/b"], provider="tavily")
    assert result.get("error")
    assert result["fallback_errors"] == [{"provider": "tavily", "error": "all_urls_failed"}]
    assert result["unmatched_results"] == [{"provider": "tavily", "url": "https://example.org/stray", "has_content": True}]


def test_requested_url_stamp_is_dropped_when_url_was_not_rewritten(monkeypatch):
    # Adapters stamp requested_url for matching; an unchanged URL must not
    # leak it into tool output or block the extraction cache.
    monkeypatch.setenv("KEENABLE_API_KEY", "test-key")
    urls = ["https://example.org/a", "https://example.org/b"]

    def answer(endpoint, *args, **kwargs):
        requested = parse_qs(urlsplit(endpoint).query)["url"][0]
        if requested.endswith("/b"):
            return {"url": "https://example.com/redirect-b", "content": "paid b"}
        return {"url": requested, "content": "paid a"}

    monkeypatch.setattr(providers, "make_get_request", answer)
    result = extract.extract_plus(urls, provider="keenable")
    assert not result.get("error")
    first, second = result["results"]
    assert "requested_url" not in first
    assert second["requested_url"] == urls[1]
