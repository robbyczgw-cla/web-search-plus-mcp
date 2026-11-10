"""MCP server: option-like values behind variadic CLI flags are refused before any run."""
import asyncio
import json

import pytest

from web_search_plus_mcp import server


def _call(name, args):
    return json.loads(asyncio.run(server.call_tool(name, args))[0].text)


@pytest.mark.parametrize("field", ["include_domains", "exclude_domains"])
@pytest.mark.parametrize("bad", ["--clear-cache", "-x", ""])
@pytest.mark.parametrize("detail", ["compact", "full"])
def test_search_rejects_option_like_domains(field, bad, detail):
    payload = _call("web_search", {"query": "q", field: [bad], "detail": detail})
    assert payload["status"] == "failed"
    if detail == "full":
        assert payload["error_v3"]["error_class"] == "invalid_request"
    else:
        assert payload["detail"] == "compact"
        assert "Invalid" in payload["error"]


@pytest.mark.parametrize("bad", [["--clear-cache"], ["-h"], [""], []])
@pytest.mark.parametrize("detail", ["compact", "full"])
def test_extract_rejects_option_like_or_empty_urls(bad, detail):
    payload = _call("web_extract", {"urls": bad, "detail": detail})
    assert payload["status"] == "failed"
    if detail == "full":
        assert payload["error_v3"]["error_class"] == "invalid_request"
    else:
        assert payload["detail"] == "compact"
        assert "Invalid" in payload["error"]


@pytest.mark.parametrize("detail", ["compact", "full"])
@pytest.mark.parametrize("length", [8193, 9000])
@pytest.mark.parametrize("shape", ["string", "batch"])
def test_extract_rejects_overlong_urls_before_provider_dispatch(monkeypatch, detail, length, shape):
    async def forbidden(*args, **kwargs):
        raise AssertionError("overlong URL reached provider dispatch")

    monkeypatch.setattr(server, "_run_cmd", forbidden)
    url = "https://example.com/" + "x" * (length - len("https://example.com/"))
    urls = url if shape == "string" else ["https://example.org/", url]
    payload = _call("web_extract", {"urls": urls, "provider": "donsetch", "detail": detail})
    assert payload["status"] == "failed"
    assert payload["error"] == "Invalid urls: entries must not exceed 8192 characters"
    if detail == "full":
        assert payload["error_v3"]["code"] == "wsp.request.invalid_arguments"
        assert payload["error_v3"]["error_class"] == "invalid_request"


def test_extract_accepts_a_url_at_the_length_limit(monkeypatch):
    seen = []

    async def capture(cmd, **kwargs):
        seen.extend(kwargs["urls"])
        return []

    monkeypatch.setattr(server, "_run_cmd", capture)
    url = "https://example.com/" + "x" * (8192 - len("https://example.com/"))
    assert asyncio.run(server.call_tool("web_extract", {"urls": [url]})) == []
    assert seen == [url]
