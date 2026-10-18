"""Requested URL evidence must survive DonSeTch redirect projection."""

import shutil

import pytest

from web_search_plus_mcp import provider_registry
from web_search_plus_mcp.extract_match import match_extract_items


@pytest.mark.parametrize("content_ok", [True, False], ids=["page", "failure"])
def test_redirected_extract_item_keeps_requested_url(monkeypatch, content_ok):
    spec = provider_registry.PROVIDER_SPECS["donsetch"]
    module = spec.execute_extract.__globals__
    requested = "https://example.org/before-redirect"
    observed = "https://example.org/after-redirect"

    class FakeSession:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def call(self, tool, arguments):
            assert tool == "web_fetch"
            assert arguments["url"] == requested
            return {
                "structured": {
                    "url": observed, "requested_url": "https://untrusted.example/wrong",
                    "content_ok": content_ok, "status": 200 if content_ok else 403,
                },
                "text": "redirected page" if content_ok else "blocked",
            }

    monkeypatch.setitem(module, "DonsetchSession", FakeSession)
    payload = spec.execute_extract(
        None, "donsetch", [requested], shutil.which("true"), "markdown",
        False, False, False, {}, False,
    )
    item, = payload["results"]
    assert item["url"] == observed
    assert item.get("requested_url") == requested
    matched, unmatched = match_extract_items([requested], payload["results"])
    assert matched == [item]
    assert unmatched == []
    if content_ok:
        assert matched[0]["content"] == "redirected page"
    else:
        assert matched[0]["error"] == "donsetch_fetch_failed"
