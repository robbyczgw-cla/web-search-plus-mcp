#!/usr/bin/env python3
"""
web-search-plus-mcp: Multi-provider web search MCP server.

MCP wrapper around the Web Search Plus v1.7 engine: 10 search providers,
5 extraction providers, quality reports, and opt-in research mode.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

__version__ = "0.2.0"

SEARCH_SCRIPT = Path(__file__).parent / "search.py"
app = Server("web-search-plus")


def _load_env_file() -> None:
    """Load .env from package dir or project root without overwriting existing env."""
    for env_file in (Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"):
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:]
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


_load_env_file()


def _append_optional(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def _append_list(cmd: list[str], flag: str, values: Any) -> None:
    if values:
        if isinstance(values, str):
            values = [values]
        cmd.append(flag)
        cmd.extend(str(v) for v in values)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description=(
                "Search the web using Web Search Plus v1.7 intelligent multi-provider routing. "
                "Supports Serper, Brave, Tavily, Exa, Querit, Linkup, Firecrawl, "
                "Perplexity, You.com, and SearXNG."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "provider": {
                        "type": "string",
                        "enum": [
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
                        ],
                        "description": "Force a specific provider, or use auto-routing.",
                        "default": "auto",
                    },
                    "count": {"type": "integer", "description": "Number of results", "default": 5, "minimum": 1, "maximum": 20},
                    "depth": {
                        "type": "string",
                        "enum": ["normal", "deep", "deep-reasoning"],
                        "description": "Exa depth: normal, deep synthesis, or deep-reasoning.",
                        "default": "normal",
                    },
                    "time_range": {"type": "string", "enum": ["hour", "day", "week", "month", "year"], "description": "Recency filter."},
                    "include_domains": {"type": "array", "items": {"type": "string"}, "description": "Restrict to these domains."},
                    "exclude_domains": {"type": "array", "items": {"type": "string"}, "description": "Exclude these domains."},
                    "mode": {"type": "string", "enum": ["normal", "research"], "default": "normal", "description": "normal fast path or opt-in research mode."},
                    "quality_report": {"type": "boolean", "default": False, "description": "Attach routing/result diagnostics."},
                    "research_time_budget": {"type": "number", "default": 55.0, "minimum": 1, "maximum": 75, "description": "Best-effort budget for research mode."},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_extract",
            description=(
                "Extract markdown or HTML from URLs using Web Search Plus extraction providers. "
                "Supports Firecrawl, Linkup, Tavily, Exa, and You.com. Prefer Linkup first for cheap clean markdown."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}, "description": "URLs to extract"},
                    "provider": {"type": "string", "enum": ["auto", "firecrawl", "linkup", "tavily", "exa", "you"], "default": "auto"},
                    "format": {"type": "string", "enum": ["markdown", "html"], "default": "markdown"},
                    "include_images": {"type": "boolean", "default": False},
                    "include_raw_html": {"type": "boolean", "default": False},
                    "render_js": {"type": "boolean", "default": False},
                },
                "required": ["urls"],
            },
        ),
    ]


async def _run_cmd(cmd: list[str], timeout: int) -> list[TextContent]:
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=timeout,
    )
    output = result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"
    return [TextContent(type="text", text=output)]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "web_search":
        query = arguments["query"]
        cmd = [
            sys.executable,
            str(SEARCH_SCRIPT),
            "--query",
            query,
            "--provider",
            arguments.get("provider", "auto"),
            "--max-results",
            str(arguments.get("count", 5)),
            "--compact",
        ]
        depth = arguments.get("depth", "normal")
        if depth != "normal":
            cmd.extend(["--exa-depth", depth])
        _append_optional(cmd, "--time-range", arguments.get("time_range"))
        _append_list(cmd, "--include-domains", arguments.get("include_domains"))
        _append_list(cmd, "--exclude-domains", arguments.get("exclude_domains"))
        mode = arguments.get("mode", "normal")
        if mode != "normal":
            cmd.extend(["--mode", mode, "--research-time-budget", str(arguments.get("research_time_budget", 55.0))])
        if _as_bool(arguments.get("quality_report", False)):
            cmd.append("--quality-report")
        return await _run_cmd(cmd, timeout=75)

    if name == "web_extract":
        urls = arguments["urls"]
        if isinstance(urls, str):
            urls = [urls]
        cmd = [
            sys.executable,
            str(SEARCH_SCRIPT),
            "--extract-urls",
            *urls,
            "--provider",
            arguments.get("provider", "auto"),
            "--format",
            arguments.get("format", "markdown"),
            "--compact",
        ]
        if _as_bool(arguments.get("include_images", False)):
            cmd.append("--extract-images")
        if _as_bool(arguments.get("include_raw_html", False)):
            cmd.append("--include-raw-html")
        if _as_bool(arguments.get("render_js", False)):
            cmd.append("--render-js")
        return await _run_cmd(cmd, timeout=90)

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
