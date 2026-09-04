import asyncio
from web_search_plus_mcp import search, server as boundary

import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("text", ["--help", "-site:reddit.com", "--", "normal query"])
@pytest.mark.parametrize("capability", ["search", "extract"])
def test_subprocess_arguments_preserve_free_text(text, capability, monkeypatch):
    seen = []

    def run(cmd, **kwargs):
        args = search.build_parser({}).parse_args(cmd[2:])
        seen.append(args.query if capability == "search" else args.spans_query)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"results": [], "query": text}), stderr="")

    monkeypatch.setattr(boundary.subprocess, "run", run)
    if capability == "search":
        arguments = {"query": text, "provider": "serper"}
    else:
        arguments = {"urls": ["https://example.org"], "provider": "serper", "spans": True, "spans_query": text}
    asyncio.run(boundary.call_tool("web_" + capability, arguments))
    assert seen == [text]
