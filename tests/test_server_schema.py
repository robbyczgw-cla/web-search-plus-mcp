import asyncio
import json
from types import SimpleNamespace

import web_search_plus_mcp.server as server


def run(coro):
    return asyncio.run(coro)


def tool_by_name(name):
    tools = run(server.list_tools())
    return next(tool for tool in tools if tool.name == name)


def test_web_search_schema_exposes_v17_providers_and_controls():
    tool = tool_by_name("web_search")
    props = tool.inputSchema["properties"]

    assert props["provider"]["enum"] == [
        "auto",
        "serper",
        "brave",
        "tavily",
        "exa",
        "querit",
        "linkup",
        "firecrawl",
        "perplexity",
        "you",
        "searxng",
    ]
    assert props["depth"]["enum"] == ["normal", "deep", "deep-reasoning"]
    assert props["mode"]["enum"] == ["normal", "research"]
    assert props["quality_report"]["type"] == "boolean"
    assert props["research_time_budget"]["maximum"] == 75


def test_web_extract_tool_is_exposed_with_linkup_first_capable_schema():
    tool = tool_by_name("web_extract")
    props = tool.inputSchema["properties"]

    assert tool.inputSchema["required"] == ["urls"]
    assert props["provider"]["enum"] == ["auto", "firecrawl", "linkup", "tavily", "exa", "you"]
    assert props["render_js"]["type"] == "boolean"
    assert props["format"]["enum"] == ["markdown", "html"]


def test_web_search_call_maps_mcp_args_to_cli(monkeypatch):
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True}), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    result = run(server.call_tool("web_search", {
        "query": "latest Hermes release",
        "provider": "linkup",
        "count": 7,
        "depth": "deep",
        "time_range": "week",
        "include_domains": ["github.com"],
        "exclude_domains": ["reddit.com"],
        "mode": "research",
        "quality_report": True,
        "research_time_budget": 12,
    }))

    cmd = seen["cmd"]
    assert "--query" in cmd and "latest Hermes release" in cmd
    assert "--provider" in cmd and "linkup" in cmd
    assert "--max-results" in cmd and "7" in cmd
    assert "--exa-depth" in cmd and "deep" in cmd
    assert "--time-range" in cmd and "week" in cmd
    assert "--include-domains" in cmd and "github.com" in cmd
    assert "--exclude-domains" in cmd and "reddit.com" in cmd
    assert "--mode" in cmd and "research" in cmd
    assert "--quality-report" in cmd
    assert "--research-time-budget" in cmd and "12" in cmd
    assert result[0].text == '{"ok": true}'


def test_web_extract_call_maps_mcp_args_to_cli(monkeypatch):
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return SimpleNamespace(returncode=0, stdout=json.dumps({"results": []}), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)

    result = run(server.call_tool("web_extract", {
        "urls": ["https://example.com"],
        "provider": "linkup",
        "format": "markdown",
        "include_images": True,
        "include_raw_html": True,
        "render_js": True,
    }))

    cmd = seen["cmd"]
    assert "--extract-urls" in cmd and "https://example.com" in cmd
    assert "--provider" in cmd and "linkup" in cmd
    assert "--format" in cmd and "markdown" in cmd
    assert "--extract-images" in cmd
    assert "--include-raw-html" in cmd
    assert "--render-js" in cmd
    assert seen["timeout"] == 90
    assert result[0].text == '{"results": []}'
