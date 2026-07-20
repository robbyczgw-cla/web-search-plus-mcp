#!/usr/bin/env python3
"""
web-search-plus-mcp: Multi-provider web search MCP server.

MCP wrapper around the Web Search Plus v3 source-only runtime: 12 search
providers, 8 extraction providers, evidence-rich responses, bounded extraction,
guarded auto-routing, and opt-in research mode.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .provider_registry import DEFAULT_AUTO_ALLOW, DEFAULT_PROVIDER_PRIORITY, EXTRACT_PROVIDER_IDS, PROVIDER_SPECS

__version__ = "1.1.0"

SEARCH_SCRIPT = Path(__file__).parent / "search.py"
app = Server("web-search-plus", version=__version__)


SEARCH_PROVIDERS = {
    provider: {
        "env": spec.env_var,
        "capabilities": [*spec.capability_labels],
        **({"auto_allow": False} if not spec.auto_allowed_by_default else {}),
    }
    for provider, spec in PROVIDER_SPECS.items()
    if spec.supports_search
}
EXTRACT_PROVIDERS = list(EXTRACT_PROVIDER_IDS)
PRESETS = {
    "starter": ["YOU_API_KEY", "SERPER_API_KEY", "LINKUP_API_KEY"],
    "minimal": ["YOU_API_KEY"],
    "lean": ["YOU_API_KEY", "LINKUP_API_KEY"],
    "all": [meta["env"] for meta in SEARCH_PROVIDERS.values()],
}

CONFIG_ENV_VAR = "WEB_SEARCH_PLUS_CONFIG"
PROVIDER_ALIASES = {"kilo_perplexity": "kilo-perplexity"}
RETIRED_ANSWER_PROVIDERS = {"perplexity", "kilo-perplexity"}
ROUTING_PROVIDER_ORDER = list(DEFAULT_PROVIDER_PRIORITY)
DEFAULT_SEARCH_SUBPROCESS_TIMEOUT_SECONDS = 75
RESEARCH_SUBPROCESS_GRACE_SECONDS = 10


def _canonical_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    return PROVIDER_ALIASES.get(value, value)


def _research_subprocess_timeout(value: Any) -> int:
    """Keep the outer process alive long enough to emit the inner budget result."""
    try:
        budget = float(value)
    except (TypeError, ValueError):
        budget = 55.0
    if not math.isfinite(budget):
        budget = 55.0
    budget = min(75.0, max(1.0, budget))
    return math.ceil(budget) + RESEARCH_SUBPROCESS_GRACE_SECONDS


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
            "extract_provider_priority": EXTRACT_PROVIDERS[:],
            "disabled_providers": [],
            "auto_allow": dict(DEFAULT_AUTO_ALLOW),
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


def _normalize_provider_list(
    value: Any, *, allow_empty: bool = True, drop_retired: bool = False
) -> list[str]:
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
        if canonical in RETIRED_ANSWER_PROVIDERS and drop_retired:
            continue
        if canonical not in SEARCH_PROVIDERS:
            raise ValueError(f"unknown provider: {provider}")
        if canonical not in normalized:
            normalized.append(canonical)
    if not normalized and not allow_empty:
        raise ValueError("provider list cannot be empty")
    return normalized


def _append_missing_default_providers(providers: list[str]) -> list[str]:
    """Preserve user order while adding newly introduced default providers."""
    merged = list(providers)
    for provider in ROUTING_PROVIDER_ORDER:
        if provider not in merged:
            merged.append(provider)
    return merged


def _normalize_extract_provider_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw = [str(part).strip() for part in value]
    else:
        raise ValueError("extract provider list must be a list or comma-separated string")
    normalized: list[str] = []
    for provider in raw:
        if not provider:
            continue
        canonical = _canonical_provider(provider)
        if canonical not in EXTRACT_PROVIDERS:
            if canonical in SEARCH_PROVIDERS:
                raise ValueError(f"provider does not support extraction: {canonical}")
            raise ValueError(f"unknown provider: {provider}")
        if canonical not in normalized:
            normalized.append(canonical)
    if not normalized:
        raise ValueError("extract provider list cannot be empty")
    return normalized


def _append_missing_extract_providers(providers: list[str]) -> list[str]:
    return list(providers) + [provider for provider in EXTRACT_PROVIDERS if provider not in providers]


def _normalize_behavior_config(
    config: dict[str, Any], *, migrate_retired: bool = False
) -> dict[str, Any]:
    normalized = _merge_dict(_default_behavior_config(), config or {})
    defaults = normalized.setdefault("defaults", {})
    default_provider = _canonical_provider(str(defaults.get("provider", "serper")))
    if default_provider in RETIRED_ANSWER_PROVIDERS and migrate_retired:
        default_provider = "serper"
    if default_provider not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown default provider: {defaults.get('provider')}")
    defaults["provider"] = default_provider
    auto = normalized.setdefault("auto_routing", {})
    auto["enabled"] = bool(auto.get("enabled", True))
    fallback = _canonical_provider(str(auto.get("fallback_provider", "serper")))
    if fallback in RETIRED_ANSWER_PROVIDERS and migrate_retired:
        fallback = "serper"
    if fallback not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown fallback provider: {auto.get('fallback_provider')}")
    auto["fallback_provider"] = fallback
    priority = _normalize_provider_list(
        auto.get("provider_priority", ROUTING_PROVIDER_ORDER),
        allow_empty=False,
        drop_retired=migrate_retired,
    )
    auto["provider_priority"] = _append_missing_default_providers(priority) if auto.get("enabled", True) is not False else priority
    extract_priority = _normalize_extract_provider_list(auto.get("extract_provider_priority", EXTRACT_PROVIDERS))
    auto["extract_provider_priority"] = _append_missing_extract_providers(extract_priority)
    auto["disabled_providers"] = _normalize_provider_list(
        auto.get("disabled_providers", []),
        allow_empty=True,
        drop_retired=migrate_retired,
    )
    raw_auto_allow = auto.get("auto_allow") or {}
    if not isinstance(raw_auto_allow, dict):
        raise ValueError("auto_allow must be an object mapping provider names to booleans")
    normalized_auto_allow = dict(_default_behavior_config()["auto_routing"]["auto_allow"])
    for provider, allowed in raw_auto_allow.items():
        canonical = _canonical_provider(str(provider))
        if canonical in RETIRED_ANSWER_PROVIDERS and migrate_retired:
            continue
        if canonical not in SEARCH_PROVIDERS:
            raise ValueError(f"unknown auto_allow provider: {provider}")
        normalized_auto_allow[canonical] = bool(allowed)
    auto["auto_allow"] = normalized_auto_allow
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
        serialized = json.dumps(data, sort_keys=True)
        retired_present = any(provider in serialized for provider in RETIRED_ANSWER_PROVIDERS)
        normalized = _normalize_behavior_config(data, migrate_retired=True)
        warning = (
            "Retired answer-only providers were ignored by the source-only 1.0 runtime."
            if retired_present
            else None
        )
        return normalized, warning
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


def _configured_env(env_name: str) -> bool:
    return bool((os.environ.get(env_name) or "").strip())


def _configured_providers() -> dict[str, bool]:
    return {name: _configured_env(meta["env"]) for name, meta in SEARCH_PROVIDERS.items()}


def _has_search_provider() -> bool:
    return any(_configured_env(meta["env"]) for meta in SEARCH_PROVIDERS.values())


def _has_extract_provider() -> bool:
    return any(_configured_env(SEARCH_PROVIDERS[p]["env"]) for p in EXTRACT_PROVIDERS)


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
                "Source-only web search through the Web Search Plus v3 runtime. "
                "Routes across 12 source-result providers and returns additive v3 evidence, "
                "routing receipts, provider attempts, cache provenance, and typed errors."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "provider": {
                        "type": "string",
                        "enum": ["auto", *SEARCH_PROVIDERS],
                        "description": "Force a specific provider, or use auto-routing.",
                        "default": "auto",
                    },
                    "count": {"type": "integer", "description": "Number of results", "default": 5, "minimum": 1, "maximum": 20},
                    "depth": {
                        "type": "string",
                        "enum": ["normal", "deep", "deep-reasoning"],
                        "description": "Exa depth: normal, deep multi-source search, or deep-reasoning.",
                        "default": "normal",
                    },
                    "time_range": {"type": "string", "enum": ["hour", "day", "week", "month", "year"], "description": "Recency filter."},
                    "freshness": {"type": "string", "enum": ["day", "week", "month", "year"], "description": "Unified recency filter alias for providers that support freshness."},
                    "search_type": {"type": "string", "enum": ["search", "news"], "default": "search", "description": "Search vertical. Serper serves news natively; other providers report unsupported metadata."},
                    "country": {"type": "string", "description": "ISO 3166-1 alpha-2 country override (e.g. at, fr)."},
                    "language": {"type": "string", "description": "ISO 639-1 language override (e.g. de), or auto via config defaults."},
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
                "Source-only URL extraction through 8 Web Search Plus v3 providers. "
                "Responses preserve bounded-context limits, truncation warnings, evidence, "
                "and page-on-demand stored-content references."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}, "description": "URLs to extract"},
                    "provider": {"type": "string", "enum": ["auto", *EXTRACT_PROVIDERS], "default": "auto"},
                    "format": {"type": "string", "enum": ["markdown", "html"], "default": "markdown"},
                    "include_images": {"type": "boolean", "default": False},
                    "include_raw_html": {"type": "boolean", "default": False},
                    "render_js": {"type": "boolean", "default": False},
                    "spans": {
                        "type": "boolean",
                        "default": False,
                        "description": "Select deterministic semantic spans from extracted text.",
                    },
                    "spans_query": {
                        "type": "string",
                        "description": "Optional query used to rank semantic spans.",
                    },
                },
                "required": ["urls"],
            },
        ),
    ]
    return tools


def _field_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("text")
    return value if isinstance(value, str) else ""


def _field_url(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("canonical") or value.get("observed")
    return value if isinstance(value, str) else ""


def _typed_error_payload(
    *,
    code: str,
    message: str,
    error_class: str,
    provider: Optional[str] = None,
    retryable: bool = False,
) -> dict[str, Any]:
    error_v3 = {
        "error_class": error_class,
        "code": code,
        "message": message,
        "retryable": retryable,
        "provider": provider,
    }
    return {
        "contract_version": "3.0",
        "status": "failed",
        "provider": provider,
        "results": [],
        "error": message,
        "error_v3": error_v3,
    }


def _project_v3_payload(
    payload: dict[str, Any],
    *,
    capability: str,
    query: Optional[str] = None,
    urls: Optional[list[str]] = None,
    request_mode: Optional[str] = None,
) -> dict[str, Any]:
    """Project canonical v3 output to the stable MCP shape, additively."""
    projected = {key: value for key, value in payload.items() if key not in {"results", "error"}}
    receipt = payload.get("routing_receipt") or {}
    if capability == "search" and request_mode == "research":
        provider = "research"
    else:
        provider = receipt.get("selected_provider")
        if not provider:
            attempts = payload.get("provider_attempts") or []
            provider = next(
                (item.get("provider") for item in attempts if item.get("outcome") == "success"),
                None,
            )
    projected["provider"] = provider
    if query is not None:
        projected["query"] = query
    if urls is not None:
        projected["urls"] = list(urls)

    results = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        url = _field_url(item.get("url"))
        if capability == "extract":
            result = {"url": url, "content": _field_text(item.get("text"))}
        else:
            result = {
                "title": _field_text(item.get("title")),
                "url": url,
                "snippet": _field_text(item.get("snippet")),
            }
        results.append(result)
    projected["results"] = results

    error_value = payload.get("error")
    error_v3 = error_value if isinstance(error_value, dict) else payload.get("error_v3")
    if isinstance(error_v3, dict):
        projected["error"] = (
            error_value.strip()
            if isinstance(error_value, str) and error_value.strip()
            else str(error_v3.get("message") or "Web Search Plus request failed")
        )
        projected["error_v3"] = error_v3
    elif isinstance(error_value, str) and error_value.strip():
        projected["error"] = error_value.strip()
    return projected


async def _run_cmd(
    cmd: list[str],
    timeout: int,
    *,
    capability: str,
    query: Optional[str] = None,
    urls: Optional[list[str]] = None,
    request_mode: Optional[str] = None,
) -> list[TextContent]:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        payload = _typed_error_payload(
            code="wsp.subprocess.timeout",
            message="Web Search Plus subprocess timed out.",
            error_class="timeout",
            retryable=True,
        )
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
    raw = (result.stdout if result.returncode == 0 else result.stderr).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = _typed_error_payload(
            code=(
                "wsp.subprocess.invalid_response"
                if result.returncode == 0
                else "wsp.subprocess.failed"
            ),
            message=(
                "Web Search Plus subprocess returned an invalid response."
                if result.returncode == 0
                else "Web Search Plus subprocess failed."
            ),
            error_class="internal",
        )
    if isinstance(payload, dict) and payload.get("contract_version") == "3.0":
        payload = _project_v3_payload(
            payload,
            capability=capability,
            query=query,
            urls=urls,
            request_mode=request_mode,
        )
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "web_search":
        query = arguments["query"]
        provider = _canonical_provider(arguments.get("provider", "auto"))
        if provider in RETIRED_ANSWER_PROVIDERS:
            payload = _typed_error_payload(
                code="wsp.provider.source_only_required",
                message=f"Provider '{provider}' is unavailable because Web Search Plus 3.0 is source-only.",
                error_class="unsupported",
                provider=provider,
            )
            return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
        cmd = [
            sys.executable,
            str(SEARCH_SCRIPT),
            "--query",
            query,
            "--provider",
            provider,
            "--max-results",
            str(arguments.get("count", 5)),
            "--compact",
            "--contract-v3",
        ]
        depth = arguments.get("depth", "normal")
        if depth != "normal":
            cmd.extend(["--exa-depth", depth])
        _append_optional(cmd, "--time-range", arguments.get("time_range"))
        _append_optional(cmd, "--freshness", arguments.get("freshness"))
        _append_optional(cmd, "--search-type", arguments.get("search_type"))
        _append_optional(cmd, "--country", arguments.get("country"))
        _append_optional(cmd, "--language", arguments.get("language"))
        _append_list(cmd, "--include-domains", arguments.get("include_domains"))
        _append_list(cmd, "--exclude-domains", arguments.get("exclude_domains"))
        mode = arguments.get("mode", "normal")
        research_time_budget = arguments.get("research_time_budget", 55.0)
        if mode != "normal":
            cmd.extend(["--mode", mode, "--research-time-budget", str(research_time_budget)])
        if _as_bool(arguments.get("quality_report", False)):
            cmd.append("--quality-report")
        return await _run_cmd(
            cmd,
            timeout=(
                _research_subprocess_timeout(research_time_budget)
                if mode == "research"
                else DEFAULT_SEARCH_SUBPROCESS_TIMEOUT_SECONDS
            ),
            capability="search",
            query=query,
            request_mode=mode,
        )

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
            "--contract-v3",
        ]
        if _as_bool(arguments.get("include_images", False)):
            cmd.append("--extract-images")
        if _as_bool(arguments.get("include_raw_html", False)):
            cmd.append("--include-raw-html")
        if _as_bool(arguments.get("render_js", False)):
            cmd.append("--render-js")
        if _as_bool(arguments.get("spans", False)):
            cmd.append("--spans")
        _append_optional(cmd, "--spans-query", arguments.get("spans_query"))
        return await _run_cmd(cmd, timeout=90, capability="extract", urls=urls)

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
        "search_configured": _has_search_provider(),
        "extract_configured": _has_extract_provider(),
        "tools_if_started_now": ["web_search", "web_extract"],
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


def _canonical_snippet(env_file: str = ".env") -> dict[str, Any]:
    env = {
        "LINKUP_API_KEY": "your_linkup_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "BRAVE_API_KEY": "your_brave_key",
    }
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


def _write_env_template(path: Path, preset: str, overwrite: bool) -> None:
    keys = PRESETS[preset]
    if path.exists() and not overwrite:
        raise SystemExit(f"Refusing to overwrite existing {path}. Pass --force to replace it.")
    lines = ["# web-search-plus-mcp provider config"]
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
    set_priority = config_sub.add_parser("set-priority", help="Set comma-separated search provider priority")
    set_priority.add_argument("providers")
    set_extract_priority = config_sub.add_parser("set-extract-priority", help="Set comma-separated extraction provider priority")
    set_extract_priority.add_argument("providers")
    set_fallback = config_sub.add_parser("set-fallback", help="Set fallback provider")
    set_fallback.add_argument("provider")
    disable_provider = config_sub.add_parser("disable", aliases=["disable-provider"], help="Disable a provider in auto-routing")
    disable_provider.add_argument("provider")
    enable_provider = config_sub.add_parser("enable", aliases=["enable-provider"], help="Re-enable a provider in auto-routing")
    enable_provider.add_argument("provider")
    set_auto_allow = config_sub.add_parser(
        "set-auto-allow",
        help="Allow or block a guarded provider from participating in auto-routing",
    )
    set_auto_allow.add_argument("provider")
    set_auto_allow.add_argument("state", choices=["on", "off"])
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
        payload = {"preset": args.preset, "env_file": str(path), "keys": PRESETS[args.preset], "snippet": _canonical_snippet(str(path))}
        if not args.dry_run:
            _write_env_template(path, args.preset, args.force)
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
        elif args.config_command == "set-extract-priority":
            config.setdefault("auto_routing", {})["extract_provider_priority"] = _normalize_extract_provider_list(args.providers)
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
        elif args.config_command == "set-auto-allow":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config.setdefault("auto_routing", {}).setdefault("auto_allow", {})[
                provider
            ] = args.state == "on"
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
