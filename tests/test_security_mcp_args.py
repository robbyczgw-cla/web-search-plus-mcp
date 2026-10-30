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
