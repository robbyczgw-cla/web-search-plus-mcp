"""MCP server: option-like values behind variadic CLI flags are refused before any run."""
import asyncio
import json

import pytest

from web_search_plus_mcp import server


def _call(name, args):
    return json.loads(asyncio.run(server.call_tool(name, args))[0].text)


@pytest.mark.parametrize("field", ["include_domains", "exclude_domains"])
@pytest.mark.parametrize("bad", ["--clear-cache", "-x", ""])
def test_search_rejects_option_like_domains(field, bad):
    payload = _call("web_search", {"query": "q", field: [bad]})
    assert payload["status"] == "failed"
    assert payload["error_v3"]["error_class"] == "invalid_request"


@pytest.mark.parametrize("bad", [["--clear-cache"], ["-h"], [""], []])
def test_extract_rejects_option_like_or_empty_urls(bad):
    payload = _call("web_extract", {"urls": bad})
    assert payload["status"] == "failed"
    assert payload["error_v3"]["error_class"] == "invalid_request"
