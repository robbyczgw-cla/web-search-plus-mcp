#!/usr/bin/env python3
"""
web-search-plus-mcp: Multi-provider web search MCP server
Provides intelligent auto-routing across Serper (Google), Tavily (research),
and Exa (neural/discovery) based on query intent.
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Load env vars from .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

SEARCH_SCRIPT = Path(__file__).parent / "search.py"
app = Server("web-search-plus")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description=(
                "Search the web using intelligent multi-provider routing. "
                "Auto-selects between Serper (Google), Tavily (research), and Exa (discovery) "
                "based on query intent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "provider": {
                        "type": "string",
                        "enum": ["auto", "serper", "tavily", "exa"],
                        "description": "Force a specific provider (default: auto)",
                        "default": "auto"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "web_search":
        raise ValueError(f"Unknown tool: {name}")

    query = arguments["query"]
    provider = arguments.get("provider", "auto")
    count = str(arguments.get("count", 5))

    cmd = [sys.executable, str(SEARCH_SCRIPT), "--query", query, "--max-results", count]
    if provider != "auto":
        cmd += ["--provider", provider]

    env = os.environ.copy()
    result = await asyncio.to_thread(
        subprocess.run, cmd, capture_output=True, text=True, env=env, timeout=30
    )

    output = result.stdout.strip() if result.returncode == 0 else f"Search error: {result.stderr.strip()}"
    return [TextContent(type="text", text=output)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
