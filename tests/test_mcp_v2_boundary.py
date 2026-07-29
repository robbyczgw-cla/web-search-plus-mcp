import asyncio
import json
from pathlib import Path
import sys

import pytest
from mcp import Client, MCPError, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import INVALID_PARAMS, TextContent

import web_search_plus_mcp.server as server

ROOT = Path(__file__).resolve().parents[1]


def run(coro):
    return asyncio.run(coro)


async def _negotiate(mode: str) -> dict[str, object]:
    async with Client(server.app, mode=mode) as client:
        tools = await client.list_tools()
        return {
            "protocol": client.protocol_version,
            "server_version": None if client.server_info is None else client.server_info.version,
            "tools": [tool.name for tool in tools.tools],
        }


def test_sdk_v2_negotiates_modern_and_legacy_stdio_eras():
    modern = run(_negotiate("auto"))
    legacy = run(_negotiate("legacy"))

    assert modern == {
        "protocol": "2026-07-28",
        "server_version": "3.4.0",
        "tools": ["web_search", "web_extract"],
    }
    assert legacy == {
        "protocol": "2025-11-25",
        "server_version": "3.4.0",
        "tools": ["web_search", "web_extract"],
    }


def test_readme_documents_dual_era_stdio_boundary():
    readme = (ROOT / "README.md").read_text()
    assert "MCP Python SDK v2" in readme
    assert "server/discover" in readme
    assert "2026-07-28" in readme
    assert "2025-11-25" in readme
    assert "stdio only" in readme


async def _negotiate_subprocess(mode: str) -> dict[str, object]:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "web_search_plus_mcp.server", "serve"],
    )
    async with Client(
        stdio_client(parameters), mode=mode, read_timeout_seconds=10
    ) as client:
        tools = await client.list_tools()
        return {
            "protocol": client.protocol_version,
            "tools": [tool.name for tool in tools.tools],
        }


def test_sdk_v2_real_stdio_process_serves_modern_and_legacy_clients():
    assert run(_negotiate_subprocess("auto")) == {
        "protocol": "2026-07-28",
        "tools": ["web_search", "web_extract"],
    }
    assert run(_negotiate_subprocess("legacy")) == {
        "protocol": "2025-11-25",
        "tools": ["web_search", "web_extract"],
    }


def test_sdk_v2_call_tool_returns_complete_result(monkeypatch):
    async def fake_call_tool(name, arguments):
        return [
            TextContent(
                type="text",
                text=json.dumps({"tool": name, "query": arguments["query"]}),
            )
        ]

    monkeypatch.setattr(server, "call_tool", fake_call_tool)

    async def scenario():
        async with Client(server.app, mode="auto") as client:
            return await client.call_tool("web_search", {"query": "MCP v2"})

    result = run(scenario())
    assert result.result_type == "complete"
    assert result.is_error is False
    assert json.loads(result.content[0].text) == {
        "tool": "web_search",
        "query": "MCP v2",
    }


def test_sdk_v2_rejects_unknown_tools_and_invalid_arguments_without_reflection():
    secret = "do-not-reflect-this-value"

    async def scenario():
        async with Client(server.app, mode="auto") as client:
            with pytest.raises(MCPError) as unknown:
                await client.call_tool("unknown_tool", {})
            with pytest.raises(MCPError) as invalid:
                await client.call_tool("web_search", {"query": [secret]})
            return unknown.value, invalid.value

    unknown, invalid = run(scenario())
    assert unknown.code == INVALID_PARAMS
    assert unknown.message == "Unknown tool: unknown_tool"
    assert invalid.code == INVALID_PARAMS
    assert "type validation failed at query" in invalid.message
    assert secret not in invalid.message


def test_sdk_v2_sanitizes_unexpected_tool_failures(monkeypatch):
    secret = "private upstream detail"

    async def explode(_name, _arguments):
        raise RuntimeError(secret)

    monkeypatch.setattr(server, "call_tool", explode)

    async def scenario():
        async with Client(server.app, mode="auto") as client:
            return await client.call_tool("web_search", {"query": "example"})

    result = run(scenario())
    payload = json.loads(result.content[0].text)
    assert result.is_error is True
    assert payload["error_v3"]["code"] == "wsp.mcp.tool_execution_failed"
    assert secret not in result.content[0].text
