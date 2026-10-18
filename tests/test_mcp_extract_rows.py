"""web_extract answers every requested URL: rows past the cap, requested_url."""

import os
import socket
from unittest import mock

import pytest

from web_search_plus_mcp import extract, providers, server
from web_search_plus_mcp.compat_v3 import legacy_request_to_v3
from web_search_plus_mcp.contract_v3 import Capability


@pytest.fixture(autouse=True)
def _public_example_hosts(monkeypatch):
    resolve = socket.getaddrinfo

    def fake(host, port, *args, **kwargs):
        if str(host).endswith("example.com"):
            host = "93.184.216.34"
        return resolve(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def _extract_through_projection(urls, answer, **options):
    """Real v3 engine with a fixed Firecrawl answer, then the MCP projection."""
    with mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}, clear=True), mock.patch.object(
        providers, "extract_firecrawl", side_effect=answer
    ):
        request = legacy_request_to_v3(
            Capability.EXTRACT, {"urls": urls, "provider": "firecrawl", **options}
        )
        response = extract.run_extract_request_v3(request, config=extract.load_config()).to_dict()
    return server._project_v3_payload(response, capability="extract", urls=urls)


def _page(url, final_url=None):
    return {
        "url": final_url or url,
        "requested_url": url,
        "title": "T",
        "content": f"text of {url}",
        "raw_content": f"text of {url}",
        "provider": "firecrawl",
    }


def _answer(batch, *args, **kwargs):
    return {"provider": "firecrawl", "results": [_page(url) for url in batch]}


def test_urls_past_the_cap_get_a_not_tried_row_in_the_mcp_output():
    urls = [f"https://example.com/page-{index}" for index in range(12)]

    projected = _extract_through_projection(urls, _answer)

    assert [item["url"] for item in projected["results"]] == urls
    assert all(item["content"] for item in projected["results"][:10])
    for item in projected["results"][10:]:
        assert item["error"] == "not tried: limit of 10 URLs per call reached"
        assert item["content"] == ""
    assert projected["limits_applied"]["extract"]["omitted_urls"] == urls[10:]


def test_requests_within_the_cap_get_no_extra_rows():
    urls = [f"https://example.com/page-{index}" for index in range(3)]

    projected = _extract_through_projection(urls, _answer)

    assert [item["url"] for item in projected["results"]] == urls
    assert not any(item.get("error") for item in projected["results"])


def test_requested_url_tells_inputs_apart_when_the_final_url_is_shared():
    urls = ["https://example.com/?ref=a", "https://example.com/?ref=b"]

    def answer(batch, *args, **kwargs):
        # The provider reports the page without the tracking parameter.
        return {"provider": "firecrawl", "results": [_page(url, "https://example.com") for url in batch]}

    projected = _extract_through_projection(urls, answer)

    assert [item["url"] for item in projected["results"]] == ["https://example.com"] * 2
    assert [item["requested_url"] for item in projected["results"]] == urls
    assert [item["content"] for item in projected["results"]] == [f"text of {url}" for url in urls]


def test_requested_url_follows_request_order_when_the_provider_reorders():
    urls = [f"https://example.com/page-{index}" for index in range(3)]

    def answer(batch, *args, **kwargs):
        return {"provider": "firecrawl", "results": [_page(url) for url in reversed(batch)]}

    projected = _extract_through_projection(urls, answer)

    assert [item["requested_url"] for item in projected["results"]] == urls
    assert [item["content"] for item in projected["results"]] == [f"text of {url}" for url in urls]


def test_failed_urls_keep_their_requested_url():
    urls = ["https://example.com/ok", "https://example.com/bad"]

    def answer(batch, *args, **kwargs):
        return {
            "provider": "firecrawl",
            "results": [
                _page(urls[0]),
                {"url": urls[1], "requested_url": urls[1], "title": "", "content": "", "error": "Firecrawl scrape failed",
                 "provider": "firecrawl"},
            ],
        }

    projected = _extract_through_projection(urls, answer)

    assert [item["requested_url"] for item in projected["results"]] == urls
    assert "error" not in projected["results"][0]
    assert projected["results"][1]["error"]


def test_blocked_urls_keep_their_requested_url():
    urls = ["https://example.com/ok", "http://127.0.0.1/admin"]

    projected = _extract_through_projection(urls, _answer)

    assert [item["requested_url"] for item in projected["results"]] == urls
    assert projected["results"][1]["error"]


def test_rate_limit_midway_keeps_pages_and_labels_every_url():
    from web_search_plus_mcp.http_client import ProviderRequestError

    urls = [f"https://example.com/page-{index}" for index in range(4)]

    def make_request(_api, _headers, body, timeout=0):
        if body["url"] == urls[2]:
            raise ProviderRequestError("Rate limited", status_code=429)
        return {"success": True, "data": {"markdown": f"text of {body['url']}", "metadata": {"title": "T"}}}

    # Drive the real Firecrawl adapter instead of a fixed answer.
    with mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}, clear=True), mock.patch.object(
        providers, "make_request", side_effect=make_request
    ):
        request = legacy_request_to_v3(Capability.EXTRACT, {"urls": urls, "provider": "firecrawl"})
        response = extract.run_extract_request_v3(request, config=extract.load_config()).to_dict()
    projected = server._project_v3_payload(response, capability="extract", urls=urls)

    assert [item["requested_url"] for item in projected["results"]] == urls
    assert [bool(item["content"]) for item in projected["results"]] == [True, True, False, False]
    assert "rate limit" in projected["results"][2]["error"]
    assert projected["results"][3]["error"] == "not tried: provider rate limit reached"
    assert any(item["outcome"] == "partial" for item in projected["provider_attempts"])


def test_results_that_do_not_line_up_with_the_request_get_no_requested_url():
    payload = {
        "results": [{
            "url": {"observed": "https://example.com/a", "canonical": "https://example.com/a"},
            "text": {"text": "body"},
        }],
        "limits_applied": {"extract": {
            "processed_urls": ["https://example.com/a", "https://example.com/b"],
            "omitted_urls": [],
        }},
    }

    projected = server._project_v3_payload(payload, capability="extract")

    assert projected["results"] == [{"url": "https://example.com/a", "content": "body"}]


def test_search_results_have_no_requested_url():
    payload = {
        "results": [{
            "url": {"observed": "https://example.com/a", "canonical": "https://example.com/a"},
            "title": {"text": "T"},
            "snippet": {"text": "S"},
        }],
    }

    projected = server._project_v3_payload(payload, capability="search", query="q")

    assert "requested_url" not in projected["results"][0]
