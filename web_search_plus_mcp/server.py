#!/usr/bin/env python3
"""
web-search-plus-mcp: Multi-provider web search MCP server.

MCP wrapper around the Web Search Plus v1.10 family: 12 search providers,
5 extraction providers, quality reports, opt-in research mode, and optional beta answers.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

__version__ = "0.6.0"

SEARCH_SCRIPT = Path(__file__).parent / "search.py"
app = Server("web-search-plus")


SEARCH_PROVIDERS = {
    "serper": {"env": "SERPER_API_KEY", "capabilities": ["search"]},
    "brave": {"env": "BRAVE_API_KEY", "capabilities": ["search"]},
    "tavily": {"env": "TAVILY_API_KEY", "capabilities": ["search", "extract"]},
    "exa": {"env": "EXA_API_KEY", "capabilities": ["search", "extract"]},
    "linkup": {"env": "LINKUP_API_KEY", "capabilities": ["search", "extract"]},
    "firecrawl": {"env": "FIRECRAWL_API_KEY", "capabilities": ["search", "extract"]},
    "perplexity": {"env": "PERPLEXITY_API_KEY", "capabilities": ["search"]},
    "kilo-perplexity": {"env": "KILOCODE_API_KEY", "capabilities": ["search"]},
    "you": {"env": "YOU_API_KEY", "capabilities": ["search", "extract"]},
    "searxng": {"env": "SEARXNG_INSTANCE_URL", "capabilities": ["search"]},
    "serpbase": {"env": "SERPBASE_API_KEY", "capabilities": ["search"], "auto_allow": False},
    "querit": {"env": "QUERIT_API_KEY", "capabilities": ["search"], "auto_allow": False},
}
EXTRACT_PROVIDERS = ["linkup", "firecrawl", "tavily", "exa", "you"]
PRESETS = {
    "starter": ["TAVILY_API_KEY", "LINKUP_API_KEY", "BRAVE_API_KEY"],
    "minimal": ["BRAVE_API_KEY"],
    "lean": ["TAVILY_API_KEY", "LINKUP_API_KEY"],
    "all": [meta["env"] for meta in SEARCH_PROVIDERS.values()],
}

CONFIG_ENV_VAR = "WEB_SEARCH_PLUS_CONFIG"
PROVIDER_ALIASES = {"kilo_perplexity": "kilo-perplexity"}
ROUTING_PROVIDER_ORDER = ["tavily", "linkup", "exa", "firecrawl", "perplexity", "kilo-perplexity", "brave", "serper", "you", "searxng", "serpbase", "querit"]


def _canonical_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    return PROVIDER_ALIASES.get(value, value)


def _valid_provider(provider: str) -> bool:
    return _canonical_provider(provider) in SEARCH_PROVIDERS


def _default_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, Path(__file__).parent.parent / "config.json")).expanduser()


def _default_behavior_config() -> dict[str, Any]:
    return {
        "defaults": {"provider": "serper", "max_results": 5},
        "auto_routing": {
            "enabled": True,
            "fallback_provider": "serper",
            "provider_priority": ROUTING_PROVIDER_ORDER[:],
            "disabled_providers": [],
            "auto_allow": {"serpbase": False, "querit": False},
            "confidence_threshold": 0.3,
        },
    }


def _merge_dict(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_provider_list(value: Any, *, allow_empty: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw = [str(part).strip() for part in value]
    else:
        raise ValueError("provider list must be a list or comma-separated string")
    normalized: list[str] = []
    for provider in raw:
        if not provider:
            continue
        canonical = _canonical_provider(provider)
        if canonical not in SEARCH_PROVIDERS:
            raise ValueError(f"unknown provider: {provider}")
        if canonical not in normalized:
            normalized.append(canonical)
    if not normalized and not allow_empty:
        raise ValueError("provider list cannot be empty")
    return normalized


def _normalize_behavior_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = _merge_dict(_default_behavior_config(), config or {})
    defaults = normalized.setdefault("defaults", {})
    default_provider = _canonical_provider(str(defaults.get("provider", "serper")))
    if default_provider not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown default provider: {defaults.get('provider')}")
    defaults["provider"] = default_provider
    auto = normalized.setdefault("auto_routing", {})
    auto["enabled"] = bool(auto.get("enabled", True))
    fallback = _canonical_provider(str(auto.get("fallback_provider", "serper")))
    if fallback not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown fallback provider: {auto.get('fallback_provider')}")
    auto["fallback_provider"] = fallback
    auto["provider_priority"] = _normalize_provider_list(auto.get("provider_priority", ROUTING_PROVIDER_ORDER), allow_empty=False)
    auto["disabled_providers"] = _normalize_provider_list(auto.get("disabled_providers", []), allow_empty=True)
    raw_auto_allow = auto.get("auto_allow", {"serpbase": False, "querit": False})
    if not isinstance(raw_auto_allow, dict):
        raise ValueError("auto_allow must be an object mapping provider names to booleans")
    auto["auto_allow"] = {_canonical_provider(str(provider)): bool(allowed) for provider, allowed in raw_auto_allow.items()}
    threshold = auto.get("confidence_threshold", 0.3)
    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence_threshold must be a number from 0 to 1") from exc
    if not 0 <= threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    auto["confidence_threshold"] = threshold
    return normalized


def _load_behavior_config(path: Optional[Path] = None) -> tuple[dict[str, Any], Optional[str]]:
    path = path or _default_config_path()
    if not path.exists():
        return _default_behavior_config(), None
    try:
        data = json.loads(path.read_text())
        return _normalize_behavior_config(data), None
    except Exception as exc:
        broken = path.with_name(path.name + f".broken-{int(__import__('time').time())}")
        try:
            path.replace(broken)
            detail = f"Invalid config moved to {broken}: {exc}"
        except OSError:
            detail = f"Invalid config ignored: {exc}"
        return _default_behavior_config(), detail


def _write_behavior_config(config: dict[str, Any], path: Optional[Path] = None, *, backup: bool = False) -> Path:
    path = path or _default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_behavior_config(config)
    if backup and path.exists():
        backup_path = path.with_name(path.name + f".bak-{int(__import__('time').time())}")
        backup_path.write_text(path.read_text())
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _web_answer_enabled() -> bool:
    return _truthy(os.environ.get("WSP_ENABLE_WEB_ANSWER"))


def _configured_env(env_name: str) -> bool:
    return bool((os.environ.get(env_name) or "").strip())


def _configured_providers() -> dict[str, bool]:
    return {name: _configured_env(meta["env"]) for name, meta in SEARCH_PROVIDERS.items()}


def _has_search_provider() -> bool:
    return any(_configured_env(meta["env"]) for meta in SEARCH_PROVIDERS.values())


def _has_extract_provider() -> bool:
    return any(_configured_env(SEARCH_PROVIDERS[p]["env"]) for p in EXTRACT_PROVIDERS)


def _detect_answer_freshness(query: str, requested: str = "none") -> Optional[str]:
    requested = requested or "none"
    if requested == "none":
        return None
    if requested != "auto":
        return requested
    q = query.lower()
    if any(term in q for term in ("today", "right now", "breaking", "live")):
        return "day"
    if any(term in q for term in ("latest", "this week", "recent", "news", "updates")):
        return "week"
    if any(term in q for term in ("this month", "past month")):
        return "month"
    return None


def _extract_json(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _run_json_cmd(cmd: list[str], timeout: int) -> dict[str, Any]:
    result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy(), timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed: {cmd[0]}")
    return _extract_json(result.stdout)


def _source_type_for_url(url: str) -> str:
    host = urlsplit(url).netloc.lower() or url.lower()
    if any(part in host for part in ("docs.", "developer.", "github.com", "readthedocs", "developer.mozilla")):
        return "docs"
    if any(part in host for part in ("reddit.com", "forum", "community", "discourse")):
        return "forum"
    if any(part in host for part in ("news", "reuters", "apnews", "bbc", "orf.at", "nytimes")):
        return "news"
    if any(part in host for part in ("shop", "amazon", "geizhals", "idealo")):
        return "shopping"
    return "web"


def _normalize_sources(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen = set()
    for item in results:
        url = item.get("url") or item.get("link") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        title = item.get("title") or url
        domain = urlsplit(url).netloc.lower()
        snippet = item.get("snippet") or item.get("description") or item.get("content") or ""
        sources.append({
            "title": title,
            "domain": domain,
            "url": url,
            "source_type": _source_type_for_url(url),
            "snippet": snippet,
            "citation": f"[{title} ({domain})]({url})",
            "used_in_answer": True,
            "extracted_status": "not_requested",
        })
        if len(sources) >= limit:
            break
    return sources


def _clean_evidence(text: str, max_chars: int = 380) -> str:
    text = " ".join((text or "").replace("\n", " ").split())
    for phrase in ("Skip to content", "Skip to main content", "You signed in with another tab or window"):
        text = text.replace(phrase, " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "…"


def _compose_answer_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    if not _web_answer_enabled():
        return {
            "error": "web_answer is optional beta and disabled. Set WSP_ENABLE_WEB_ANSWER=1 in this MCP server's env to expose and use it.",
            "enabled": False,
        }
    if not _has_search_provider():
        return {
            "error": "web_answer needs at least one search provider key configured.",
            "required": "Set one of SERPER_API_KEY, BRAVE_API_KEY, TAVILY_API_KEY, EXA_API_KEY, LINKUP_API_KEY, FIRECRAWL_API_KEY, PERPLEXITY_API_KEY, KILOCODE_API_KEY, YOU_API_KEY, SEARXNG_INSTANCE_URL, SERPBASE_API_KEY, or QUERIT_API_KEY.",
        }

    query = arguments["query"]
    mode = arguments.get("mode", "quick") if arguments.get("mode", "quick") in {"quick", "deep"} else "quick"
    source_count = int(arguments.get("sources") or (6 if mode == "deep" else 3))
    source_count = max(1, min(source_count, 10))
    max_extracts = int(arguments.get("max_extracts") or (3 if mode == "deep" else 2))
    max_extracts = max(0, min(max_extracts, 5, source_count))
    freshness = arguments.get("freshness", "none")
    applied_freshness = _detect_answer_freshness(query, freshness)

    cmd = [sys.executable, str(SEARCH_SCRIPT), "--query", query, "--provider", "auto", "--max-results", str(source_count), "--compact", "--quality-report"]
    if mode == "deep":
        cmd.extend(["--mode", "research", "--research-time-budget", "30"])
    if applied_freshness:
        cmd.extend(["--time-range", applied_freshness])

    try:
        search_data = _run_json_cmd(cmd, timeout=45 if mode == "deep" else 30)
    except Exception as exc:
        return {"error": str(exc), "stage": "search", "query": query, "beta": True}
    sources = _normalize_sources(search_data.get("results", [])[:source_count], source_count)
    warnings: list[str] = []
    extract_data: dict[str, Any] = {"results": []}
    urls = [s["url"] for s in sources[:max_extracts]]
    if urls and _has_extract_provider() and max_extracts > 0:
        extract_cmd = [sys.executable, str(SEARCH_SCRIPT), "--extract-urls", *urls, "--provider", "linkup" if _configured_env("LINKUP_API_KEY") else "auto", "--format", "markdown", "--compact"]
        try:
            extract_data = _run_json_cmd(extract_cmd, timeout=35 if mode == "deep" else 20)
        except Exception as exc:  # best-effort beta layer
            warnings.append(f"Extraction failed: {exc}")
            extract_data = {"results": [], "error": str(exc)}
    elif urls and max_extracts > 0:
        warnings.append("Extraction skipped: no extraction-capable provider configured. Add LINKUP_API_KEY, FIRECRAWL_API_KEY, TAVILY_API_KEY, EXA_API_KEY, or YOU_API_KEY for fuller citations.")

    extracted_by_url = {r.get("url"): r for r in extract_data.get("results", []) if isinstance(r, dict)}
    lines = [f"Source-backed brief for: {query}", ""]
    for idx, src in enumerate(sources[:max(1, max_extracts or source_count)], 1):
        extracted = extracted_by_url.get(src["url"], {})
        raw = extracted.get("content") or extracted.get("raw_content") or src.get("snippet") or ""
        if extracted:
            src["extracted_status"] = "full" if (extracted.get("content") or extracted.get("raw_content")) else "partial"
        evidence = _clean_evidence(raw) or "No readable snippet available."
        lines.append(f"- [{idx}] {src['title']} — {evidence}")
    answer = "\n".join(lines).strip()
    extracted_count = sum(1 for s in sources if s.get("extracted_status") in {"full", "partial"})
    confidence = "high" if len(sources) >= 4 and extracted_count >= 3 else "medium" if sources else "low"
    return {
        "query": query,
        "mode": mode,
        "beta": True,
        "answer": answer,
        "confidence": confidence,
        "freshness": {"requested": freshness, "applied": applied_freshness or "none"},
        "sources": sources,
        "warnings": warnings,
        "search": {"provider": search_data.get("provider"), "routing": search_data.get("routing", {})},
        "extraction": {"provider": extract_data.get("provider"), "requested_urls": urls},
    }


def _format_answer_payload(payload: dict[str, Any], output: str = "answer") -> str:
    if output == "json" or payload.get("error"):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if output == "sources":
        return "\n".join(f"- {s['citation']} — {s['source_type']}" for s in payload.get("sources", []))
    answer = payload.get("answer", "")
    if output == "brief":
        answer = answer[:900]
    lines = ["**Answer**", answer, "", "**Sources**"]
    lines.extend(f"- {s['citation']} — {s['source_type']}" for s in payload.get("sources", []))
    lines.append("")
    lines.append(f"**Confidence:** {payload.get('confidence', 'unknown')}")
    lines.append(f"**Freshness:** {payload.get('freshness', {}).get('applied', 'none')}")
    if payload.get("warnings"):
        lines.append("**Warnings:** " + "; ".join(payload["warnings"]))
    return "\n".join(lines).strip()


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
    tools = [
        Tool(
            name="web_search",
            description=(
                "Search the web using Web Search Plus v1.10 intelligent multi-provider routing. "
                "Supports Serper, Brave, Tavily, Exa, Linkup, Firecrawl, "
                "native Perplexity, Kilo Perplexity, You.com, SearXNG, SerpBase, and Querit. "
                "SerpBase and Querit are explicit-only by default and are not auto-routed unless auto_allow is changed."
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
                            "linkup",
                            "firecrawl",
                            "perplexity",
                            "kilo-perplexity",
                            "you",
                            "searxng",
                            "serpbase",
                            "querit",
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
    if _web_answer_enabled():
        tools.append(
            Tool(
                name="web_answer",
                description=(
                    "Optional beta cited-answer synthesis. Use only when the user explicitly wants a written answer or cited summary. "
                    "For source discovery, current events, prices, weather, sports lineups, schedules, and raw search landscape, use web_search. "
                    "Usually slower than web_search."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Question or topic to answer from web sources"},
                        "mode": {"type": "string", "enum": ["quick", "deep"], "default": "quick"},
                        "sources": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                        "freshness": {"type": "string", "enum": ["none", "auto", "day", "week", "month", "year"], "default": "none", "description": "Optional recency filter; default none avoids over-triggering stale/wrong current filters."},
                        "max_extracts": {"type": "integer", "default": 2, "minimum": 0, "maximum": 5},
                        "output": {"type": "string", "enum": ["answer", "brief", "sources", "json"], "default": "answer"},
                    },
                    "required": ["query"],
                },
            )
        )
    return tools


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
            _canonical_provider(arguments.get("provider", "auto")),
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

    if name == "web_answer":
        payload = await asyncio.to_thread(_compose_answer_payload, arguments)
        return [TextContent(type="text", text=_format_answer_payload(payload, arguments.get("output", "answer")))]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def _status_payload() -> dict[str, Any]:
    configured = _configured_providers()
    behavior_config, config_warning = _load_behavior_config()
    payload = {
        "version": __version__,
        "server": "web-search-plus-mcp",
        "web_answer_enabled": _web_answer_enabled(),
        "search_configured": _has_search_provider(),
        "extract_configured": _has_extract_provider(),
        "tools_if_started_now": ["web_search", "web_extract"] + (["web_answer"] if _web_answer_enabled() else []),
        "config_path": str(_default_config_path()),
        "routing_preferences": behavior_config.get("auto_routing", {}),
        "default_provider": behavior_config.get("defaults", {}).get("provider"),
        "providers": {
            name: {"env": SEARCH_PROVIDERS[name]["env"], "configured": ok, "capabilities": SEARCH_PROVIDERS[name]["capabilities"]}
            for name, ok in configured.items()
        },
    }
    if config_warning:
        payload["config_warning"] = config_warning
    return payload


def _canonical_snippet(env_file: str = ".env", enable_answer: bool = False) -> dict[str, Any]:
    env = {
        "LINKUP_API_KEY": "your_linkup_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "BRAVE_API_KEY": "your_brave_key",
    }
    if enable_answer:
        env["WSP_ENABLE_WEB_ANSWER"] = "1"
    return {
        "mcpServers": {
            "web-search-plus": {
                "command": "uvx",
                "args": ["web-search-plus-mcp"],
                "env": env,
            }
        },
        "note": f"You can also put provider keys in {env_file} next to the project/package.",
    }


def _write_env_template(path: Path, preset: str, enable_answer: bool, overwrite: bool) -> None:
    keys = PRESETS[preset]
    if path.exists() and not overwrite:
        raise SystemExit(f"Refusing to overwrite existing {path}. Pass --force to replace it.")
    lines = ["# web-search-plus-mcp provider config"]
    if enable_answer:
        lines.append("WSP_ENABLE_WEB_ANSWER=1")
    for key in keys:
        lines.append(f"{key}=")
    path.write_text("\n".join(lines) + "\n")


def cli_main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="web-search-plus-mcp server and onboarding CLI")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the MCP stdio server")
    status = sub.add_parser("status", help="Show configured providers and exposed tools")
    status.add_argument("--json", action="store_true")
    list_p = sub.add_parser("list", help="List providers or presets")
    list_p.add_argument("what", choices=["providers", "presets"])
    setup = sub.add_parser("setup", help="Write a provider .env template and print MCP config snippet")
    setup.add_argument("--preset", choices=sorted(PRESETS), default="starter")
    setup.add_argument("--env-file", default=".env")
    setup.add_argument("--enable-answer", action="store_true", default=False, help="Include WSP_ENABLE_WEB_ANSWER=1 in the generated env/snippet")
    setup.add_argument("--dry-run", action="store_true")
    setup.add_argument("--force", action="store_true")
    setup.add_argument("--json", action="store_true")
    config_p = sub.add_parser("config", help="Inspect or change routing preferences in config.json")
    config_p.add_argument("--config-path", help=f"Override config path instead of {CONFIG_ENV_VAR}/default")
    config_sub = config_p.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Show current routing preferences")
    set_default = config_sub.add_parser("set-default", help="Use one provider strictly when auto-routing is off")
    set_default.add_argument("provider")
    set_routing = config_sub.add_parser("set-routing", help="Turn auto-routing on or off")
    set_routing.add_argument("state", choices=["on", "off"])
    set_priority = config_sub.add_parser("set-priority", help="Set comma-separated provider priority")
    set_priority.add_argument("providers")
    set_fallback = config_sub.add_parser("set-fallback", help="Set fallback provider")
    set_fallback.add_argument("provider")
    disable_provider = config_sub.add_parser("disable", aliases=["disable-provider"], help="Disable a provider in auto-routing")
    disable_provider.add_argument("provider")
    enable_provider = config_sub.add_parser("enable", aliases=["enable-provider"], help="Re-enable a provider in auto-routing")
    enable_provider.add_argument("provider")
    set_threshold = config_sub.add_parser("set-threshold", help="Set confidence threshold from 0 to 1")
    set_threshold.add_argument("threshold", type=float)
    reset = config_sub.add_parser("reset", help="Reset routing preferences to defaults")
    reset.add_argument("--yes", action="store_true", help="Confirm reset")
    args = parser.parse_args(argv)

    if args.command in (None, "serve"):
        run()
        return 0
    if args.command == "status":
        payload = _status_payload()
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"web-search-plus-mcp {__version__}")
            print("Tools if started now: " + ", ".join(payload["tools_if_started_now"]))
            print(f"Search configured: {'yes' if payload['search_configured'] else 'no'}")
            print(f"Extraction configured: {'yes' if payload['extract_configured'] else 'no'}")
            print(f"web_answer beta enabled: {'yes' if payload['web_answer_enabled'] else 'no'}")
            for name, meta in payload["providers"].items():
                mark = "✓" if meta["configured"] else "·"
                print(f"  {mark} {name}: {meta['env']} ({', '.join(meta['capabilities'])})")
        return 0 if payload["search_configured"] else 1
    if args.command == "list":
        if args.what == "providers":
            for name, meta in SEARCH_PROVIDERS.items():
                print(f"{name}: {meta['env']} ({', '.join(meta['capabilities'])})")
        else:
            for name, keys in PRESETS.items():
                print(f"{name}: {', '.join(keys)}")
        return 0
    if args.command == "setup":
        path = Path(args.env_file).expanduser()
        payload = {"preset": args.preset, "env_file": str(path), "keys": PRESETS[args.preset], "web_answer_enabled": args.enable_answer, "snippet": _canonical_snippet(str(path), args.enable_answer)}
        if not args.dry_run:
            _write_env_template(path, args.preset, args.enable_answer, args.force)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            action = "Would write" if args.dry_run else "Wrote"
            print(f"{action} {path} with preset {args.preset}: {', '.join(PRESETS[args.preset])}")
            print("\nCanonical MCP stdio snippet:")
            print(json.dumps(payload["snippet"], indent=2))
        return 0
    if args.command == "config":
        if args.config_path:
            os.environ[CONFIG_ENV_VAR] = args.config_path
        path = _default_config_path()
        config, warning = _load_behavior_config(path)
        if args.config_command == "show":
            payload = {"config_path": str(path), "default_provider": config.get("defaults", {}).get("provider"), "routing_preferences": config.get("auto_routing", {})}
            if warning:
                payload["warning"] = warning
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        if args.config_command == "reset":
            if not args.yes:
                raise SystemExit("Refusing to reset without --yes")
            _write_behavior_config(_default_behavior_config(), path, backup=True)
            print(f"Reset routing preferences in {path}")
            return 0
        if args.config_command == "set-default":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config.setdefault("defaults", {})["provider"] = provider
            config.setdefault("auto_routing", {})["enabled"] = False
        elif args.config_command == "set-routing":
            config.setdefault("auto_routing", {})["enabled"] = args.state == "on"
        elif args.config_command == "set-priority":
            config.setdefault("auto_routing", {})["provider_priority"] = _normalize_provider_list(args.providers, allow_empty=False)
        elif args.config_command == "set-fallback":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config.setdefault("auto_routing", {})["fallback_provider"] = provider
        elif args.config_command in {"disable", "disable-provider"}:
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            disabled = _normalize_provider_list(config.setdefault("auto_routing", {}).get("disabled_providers", []))
            if provider not in disabled:
                disabled.append(provider)
            config["auto_routing"]["disabled_providers"] = disabled
        elif args.config_command in {"enable", "enable-provider"}:
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            disabled = _normalize_provider_list(config.setdefault("auto_routing", {}).get("disabled_providers", []))
            config["auto_routing"]["disabled_providers"] = [p for p in disabled if p != provider]
        elif args.config_command == "set-threshold":
            config.setdefault("auto_routing", {})["confidence_threshold"] = args.threshold
        _write_behavior_config(config, path)
        updated, _ = _load_behavior_config(path)
        print(json.dumps({"config_path": str(path), "default_provider": updated.get("defaults", {}).get("provider"), "routing_preferences": updated.get("auto_routing", {})}, indent=2, ensure_ascii=False))
        return 0
    parser.error("unknown command")
    return 2


def run():
    asyncio.run(main())


if __name__ == "__main__":
    raise SystemExit(cli_main())
