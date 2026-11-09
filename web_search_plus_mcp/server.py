#!/usr/bin/env python3
"""
web-search-plus-mcp: Multi-provider web search MCP server.

MCP wrapper around the Web Search Plus v3 source-only runtime: 15 search
providers, 9 extraction providers, evidence-rich responses, bounded extraction,
guarded auto-routing, and opt-in research mode.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import math
import os
import subprocess
import sys
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from .provider_registry import DEFAULT_AUTO_ALLOW, DEFAULT_PROVIDER_PRIORITY, EXTRACT_PROVIDER_IDS, PROVIDER_SPECS
from . import jev_setup
from .env_loader import candidate_env_paths, clean_env_value
from .config import runtime_config_path, validate_config_candidate, _unique_timestamped_path
from .daemon_tasks import DaemonTask

from . import __version__

SEARCH_SCRIPT = Path(__file__).parent / "search.py"


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
DETAIL_ENV_VAR = "WEB_SEARCH_PLUS_MCP_DETAIL"
DETAIL_SCHEMA = {
    "type": "string",
    "enum": ["compact", "full"],
    "description": "Response detail: compact by default; full returns the complete v3 contract. Overrides the server default.",
}
PROVIDER_ALIASES = {"kilo_perplexity": "kilo-perplexity"}
RETIRED_ANSWER_PROVIDERS = {"perplexity", "kilo-perplexity"}
ROUTING_PROVIDER_ORDER = list(DEFAULT_PROVIDER_PRIORITY)
DEFAULT_SEARCH_SUBPROCESS_TIMEOUT_SECONDS = 75
DEFAULT_DONSETCH_SUBPROCESS_TIMEOUT_SECONDS = 195
RESEARCH_SUBPROCESS_GRACE_SECONDS = 10


def _canonical_provider(provider: str) -> str:
    value = (provider or "").strip().lower()
    return PROVIDER_ALIASES.get(value, value)


def _donsetch_outer_budget_applies(provider: str) -> bool:
    return provider == "donsetch" or (
        provider == "auto" and bool(os.environ.get("DONSETCH_BIN"))
    )


def _default_behavior_config() -> dict[str, Any]:
    return {
        "mcp": {"detail": "compact"},
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


def _normalize_behavior_config(
    config: dict[str, Any], *, migrate_retired: bool = False
) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    normalized = _merge_dict(_default_behavior_config(), config)
    mcp = normalized.get("mcp")
    if not isinstance(mcp, dict) or mcp.get("detail") not in {"compact", "full"}:
        raise ValueError("mcp.detail must be compact or full")
    defaults = normalized["defaults"]
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object")
    # Existing top-level values retain the engine's precedence. New explicit
    # set-default writes synchronize both keys, so old readers keep working.
    if normalized.get("default_provider"):
        defaults["provider"] = normalized["default_provider"]
    default_provider = _canonical_provider(str(defaults["provider"]))
    if default_provider in RETIRED_ANSWER_PROVIDERS and migrate_retired:
        default_provider = "serper"
    if default_provider not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown default provider: {defaults.get('provider')}")
    defaults["provider"] = default_provider
    auto = normalized["auto_routing"]
    if not isinstance(auto, dict):
        raise ValueError("auto_routing must be an object")
    auto["enabled"] = bool(auto["enabled"])
    fallback = _canonical_provider(str(auto["fallback_provider"]))
    if fallback in RETIRED_ANSWER_PROVIDERS and migrate_retired:
        fallback = "serper"
    if fallback not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown fallback provider: {auto.get('fallback_provider')}")
    auto["fallback_provider"] = fallback
    priority = _normalize_provider_list(
        auto["provider_priority"] or ROUTING_PROVIDER_ORDER,
        allow_empty=False,
        drop_retired=migrate_retired,
    )
    auto["provider_priority"] = (
        priority + [provider for provider in ROUTING_PROVIDER_ORDER if provider not in priority]
        if auto["enabled"] else priority
    )
    # Same rule as the engine (config.py): an empty list means the default order.
    extract_priority = _normalize_extract_provider_list(auto["extract_provider_priority"] or EXTRACT_PROVIDERS)
    auto["extract_provider_priority"] = extract_priority + [provider for provider in EXTRACT_PROVIDERS if provider not in extract_priority]
    auto["disabled_providers"] = _normalize_provider_list(
        auto["disabled_providers"],
        allow_empty=True,
        drop_retired=migrate_retired,
    )
    raw_auto_allow = auto["auto_allow"] or {}
    if not isinstance(raw_auto_allow, dict):
        raise ValueError("auto_allow must be an object mapping provider names to booleans")
    normalized_auto_allow = dict(DEFAULT_AUTO_ALLOW)
    for provider, allowed in raw_auto_allow.items():
        canonical = _canonical_provider(str(provider))
        if canonical in RETIRED_ANSWER_PROVIDERS and migrate_retired:
            continue
        if canonical not in SEARCH_PROVIDERS:
            raise ValueError(f"unknown auto_allow provider: {provider}")
        normalized_auto_allow[canonical] = bool(allowed)
    auto["auto_allow"] = normalized_auto_allow
    threshold = auto["confidence_threshold"]
    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence_threshold must be a number from 0 to 1") from exc
    if not 0 <= threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    auto["confidence_threshold"] = threshold
    return normalized


def _load_behavior_config(
    path: Optional[Path] = None, *, quarantine: bool = False
) -> tuple[dict[str, Any], Optional[str]]:
    """Read the behaviour config; an invalid file falls back to defaults.

    Read paths (every tool call resolves ``detail`` here, and ``status``) leave
    the file alone: the engine is the authority on what the runtime uses, and a
    stricter check here once moved a config the engine accepted, silently
    dropping its disabled providers. Explicit recovery callers can request
    ``quarantine`` to keep a backup. CLI edits use a strict reader instead and
    reject invalid drafts without moving the original file.
    """
    path = path or runtime_config_path()
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
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as exc:
        # File decoding and normalization of untrusted JSON can fail; reads must
        # still return MCP defaults without changing the operator's file.
        if not quarantine:
            return _default_behavior_config(), f"Invalid config ignored by the MCP server settings: {exc}"
        broken = _unique_timestamped_path(path, "broken")
        try:
            path.replace(broken)
            detail = f"Invalid config moved to {broken}: {exc}"
        except OSError:
            detail = f"Invalid config ignored: {exc}"
        return _default_behavior_config(), detail


def _write_behavior_config(config: dict[str, Any], path: Optional[Path] = None, *, backup: bool = False) -> Path:
    path = path or runtime_config_path()
    normalized = _normalize_behavior_config(config)
    validate_config_candidate(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        backup_path = _unique_timestamped_path(path, "bak")
        backup_path.write_text(path.read_text())
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def _read_config_for_edit(path: Path) -> dict[str, Any]:
    """Read the actual draft; never replace unreadable policy with defaults."""
    if not path.exists():
        return _default_behavior_config()
    try:
        data = json.loads(path.read_text())
        return _normalize_behavior_config(data, migrate_retired=True)
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"Config unchanged at {path}: {exc}") from exc


def _write_cli_config(config: dict[str, Any], path: Path, *, backup: bool = False) -> Path:
    try:
        return _write_behavior_config(config, path, backup=backup)
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"Config unchanged at {path}: {exc}") from exc


_DETAIL_ENV_WARNED = False


def _resolve_detail(arguments: dict[str, Any]) -> str:
    """Resolve argument > environment > normalized config > compact.

    Invalid operator environment values warn once and fall through to config;
    invalid explicit tool arguments retain the caller-facing validation error.
    """
    global _DETAIL_ENV_WARNED
    if "detail" in arguments:
        detail = arguments["detail"]
        if detail not in ("compact", "full"):
            raise ValueError("detail must be compact or full")
        return detail
    value = os.environ.get(DETAIL_ENV_VAR, "").strip().lower()
    if value in ("compact", "full"):
        return value
    if value and not _DETAIL_ENV_WARNED:
        _DETAIL_ENV_WARNED = True
        print(
            json.dumps({"warning": f"{DETAIL_ENV_VAR} must be compact or full; ignoring it"}),
            file=sys.stderr,
        )
    config, _warning = _load_behavior_config()
    return config["mcp"]["detail"]


def _load_env_file() -> None:
    """Load .env from package dir or project root without overwriting existing env.

    Empty values and template placeholders (``your_brave_key``) are skipped: set
    first, they blocked the real key from ``$HERMES_HOME/.env``, which the
    engine's own loader reads later and also never overwrites.
    """
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
            value = clean_env_value(val)
            if value is not None:
                os.environ.setdefault(key.strip(), value)


_load_env_file()


def _append_optional(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def _unsafe_variadic_values(label: str, values: Any) -> Optional[str]:
    """Return a problem text when values are unsafe behind a variadic CLI flag.

    argparse in the child would read an entry such as ``--clear-cache`` as a
    real option, so these are refused before any process or in-process run.
    """
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return f"Invalid {label}: expected a list of strings"
    for value in values:
        if not isinstance(value, str) or not value.strip():
            return f"Invalid {label}: entries must be non-empty strings"
        if value.startswith("-"):
            return f"Invalid {label}: entries must not start with '-'"
    return None


def _invalid_arguments_payload(message: str, *, detail: str = "full") -> list[TextContent]:
    payload = _typed_error_payload(
        code="wsp.request.invalid_arguments",
        message=message,
        error_class="invalid_request",
    )
    if detail == "compact":
        payload = _compact_payload(payload, capability="search")
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


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


async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description=(
                "Source-only web search through the Web Search Plus v3 runtime. "
                "Routes across configured source-result providers. Returns compact sources by default; "
                "detail='full' includes the complete v3 evidence and routing contract."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "detail": DETAIL_SCHEMA.copy(),
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
                    "search_type": {"type": "string", "enum": ["search", "news"], "default": "search", "description": "Search vertical. Serper and TinyFish serve news natively; other providers report unsupported metadata."},
                    "country": {"type": "string", "description": "ISO 3166-1 alpha-2 country override (e.g. at, fr)."},
                    "language": {"type": "string", "description": "ISO 639-1 language override (e.g. de), or auto via config defaults."},
                    "include_domains": {"type": "array", "items": {"type": "string"}, "description": "Restrict to these domains."},
                    "exclude_domains": {"type": "array", "items": {"type": "string"}, "description": "Exclude these domains."},
                    "mode": {"type": "string", "enum": ["normal", "research"], "default": "normal", "description": "normal fast path or opt-in research mode."},
                    "quality_report": {"type": "boolean", "default": False, "description": "Attach routing/result diagnostics."},
                    "research_time_budget": {"type": "number", "default": 55.0, "minimum": 1, "maximum": 75, "description": "Best-effort budget for research mode."},
                    "no_cache": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass the search cache and fetch live results. Use for recency queries when a cached hit would be stale.",
                    },
                    "cache_ttl": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 86400,
                        "description": "Search-cache TTL in seconds. Default is 3600 if omitted.",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_extract",
            description=(
                "Source-only URL extraction through 9 Web Search Plus v3 providers. "
                "Returns bounded page text, truncation warnings and stored-content references. "
                "Compact by default; detail='full' includes the complete v3 contract."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "detail": DETAIL_SCHEMA.copy(),
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


def _field_text(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("text")
    return value if isinstance(value, str) else ""


def _field_url(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("canonical") or value.get("observed")
    return value if isinstance(value, str) else ""


def _quality_report_from_v3(
    payload: dict[str, Any], projected: dict[str, Any]
) -> dict[str, Any]:
    """Build MCP diagnostics from validated canonical evidence without re-fetching."""
    domains = []
    for item in projected["results"]:
        domain = urlparse(item["url"]).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            domains.append(domain)
    unique_domains = sorted(set(domains))
    receipt = payload.get("routing_receipt") or {}
    attempts = payload.get("provider_attempts") or []
    return {
        "query": projected.get("query") or "",
        "selected_provider": projected.get("provider"),
        "routing_policy": receipt.get("policy_id"),
        "providers_considered": list(receipt.get("candidate_order") or []),
        "provider_attempts": [
            {
                key: deepcopy(item[key])
                for key in ("provider", "outcome", "skip_reason", "error")
                if key in item
            }
            for item in attempts
            if isinstance(item, dict)
        ],
        "result_count": len(projected["results"]),
        "domain_count": len(unique_domains),
        "domains": unique_domains,
        "domain_diversity": (
            len(unique_domains) / len(domains) if domains else 0.0
        ),
        "source_diversity": deepcopy(payload.get("source_diversity") or {}),
        "cache_disposition": (payload.get("cache_status") or {}).get("disposition"),
    }


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


def _freshness_from_v3_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("freshness"), dict):
        return metadata["freshness"]
    for warning in payload.get("warnings") or []:
        if not isinstance(warning, dict):
            continue
        details = warning.get("details")
        if warning.get("code") != "wsp.freshness.applied" or not isinstance(details, dict):
            continue
        freshness = details.get("freshness")
        if isinstance(freshness, dict):
            return freshness
    return None


def _short_message(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("message") or value.get("code") or value.get("error_class")
    return " ".join(str(value or "").split())[:240]


def _compact_payload(
    projected: dict[str, Any],
    *,
    capability: str,
    canonical: Optional[dict[str, Any]] = None,
    requested_provider: Optional[str] = None,
) -> dict[str, Any]:
    """Keep model-facing data without repeating the v3 execution evidence."""
    canonical = canonical or projected
    compact = {
        "detail": "compact",
        "hint": 'Use detail="full" for the complete v3 contract.',
        "provider": projected.get("provider"),
        "results": [],
    }
    for key in ("query", "status", "error_type", "env_vars", "how_to_fix"):
        if key in projected:
            compact[key] = deepcopy(projected[key])
    error_v3 = projected.get("error_v3") or {}
    guidance = error_v3.get("details") or {}
    # An auto-routed setup error has no provider failures: every candidate was
    # unconfigured and their attempts are the fallback filler ("serper: Missing
    # API key"). An explicit request's attempt is the user's own provider.
    setup_error = guidance.get("error_type") in {"provider_setup_required", "explicit_only_provider_configured"}
    for key in ("how_to_fix", "env_var", "env_vars", "setup_required"):
        if key in guidance:
            compact.setdefault(key, deepcopy(guidance[key]))
    observations = {
        item.get("observation_id"): item
        for item in canonical.get("observations") or []
        if isinstance(item, dict)
    }
    stored = {
        item.get("observation_id"): item
        for item in canonical.get("stored_content") or []
        if isinstance(item, dict)
    }
    originals = [item for item in canonical.get("results") or [] if isinstance(item, dict)]
    fields = (
        ("url", "requested_url", "title", "content", "error", "full_text", "spans", "span_contract_version")
        if capability == "extract"
        else ("title", "url", "snippet", "published", "published_at", "date", "source_type", "fetch_priority")
    )
    for index, item in enumerate(projected["results"]):
        result = {key: deepcopy(item[key]) for key in fields if key in item}
        if capability != "extract":
            snippet = result["snippet"]
            # Preserve short snippets verbatim. Only long snippets collapse
            # whitespace and prefer a word boundary for the compact limit.
            if len(snippet) > _COMPACT_SNIPPET_CHARS:
                flat = " ".join(snippet.split())
                if len(flat) <= _COMPACT_SNIPPET_CHARS:
                    result["snippet"] = flat
                else:
                    cut = flat[: _COMPACT_SNIPPET_CHARS + 1].rpartition(" ")[0]
                    if len(cut) < _COMPACT_SNIPPET_CHARS // 2:
                        cut = flat[:_COMPACT_SNIPPET_CHARS]
                    shown = f"{cut} … [TRUNCATED: showing first {len(cut)} of {len(snippet)} characters]"
                    result["snippet"] = shown if len(shown) < len(flat) else flat
        original = originals[index] if index < len(originals) else {}
        observation_id = original.get("representative_observation_id")
        observation = observations.get(observation_id) or {}
        if capability == "extract":
            result.setdefault("requested_url", result.get("url"))
            result.setdefault("title", _field_text(original.get("title")))
            storage = stored.get(observation_id)
            if storage:
                succeeded = storage.get("storage_succeeded") is True
                result["full_text"] = {"truncated": True, "stored": succeeded}
                if succeeded:
                    result["full_text"].update({
                        "reference": deepcopy(storage.get("reference")),
                        "chars": storage.get("full_text_chars"),
                        "sha256": storage.get("full_text_sha256"),
                    })
        else:
            for key, value_key in (("source_type", "value"), ("fetch_priority", "tier")):
                if isinstance(result.get(key), dict):
                    result[key] = result[key].get(value_key)
            published = observation.get("published_at") or original.get("published_at")
            if isinstance(published, dict):
                published = published.get("normalized") or published.get("raw")
            if published:
                result["published"] = published
        compact["results"].append(result)

    attempts = [item for item in projected.get("provider_attempts") or [] if isinstance(item, dict)]
    receipt = projected.get("routing_receipt") or {}
    if receipt:
        routing = {}
        if requested_provider is not None:
            routing["auto_routed"] = requested_provider == "auto"
        # The receipt's fallback_reason is "none" without a fallback; only a real
        # fallback is worth a field, and it is named for what it is.
        fallback_reason = receipt.get("fallback_reason")
        if fallback_reason and str(fallback_reason).lower() != "none" and not setup_error:
            routing["fallback_reason"] = _short_message(fallback_reason)
        fallback = []
        for attempt in attempts:
            if (
                attempt.get("provider") == projected.get("provider")
                and attempt.get("outcome") in {"success", "partial"}
                and attempt.get("result_count", 1) > 0
            ):
                break
            failed_or_empty = attempt.get("outcome") in {"failed", "empty"} or (
                attempt.get("outcome") == "success" and attempt.get("result_count") == 0
            )
            if failed_or_empty and attempt.get("provider") not in fallback:
                fallback.append(attempt.get("provider"))
        if fallback and projected.get("provider") != "research" and not setup_error:
            routing["fallback_from"] = fallback
        if routing:
            compact["routing"] = routing

    cache = projected.get("cache_status") or {}
    if cache:
        compact["cached"] = cache.get("disposition") in {"fresh_hit", "stale_hit"}
        if cache.get("age_seconds") is not None:
            compact["cache_age_seconds"] = cache["age_seconds"]
    if projected.get("provider") == "research":
        extraction_attempts = [item for item in attempts if item.get("capability") == "extract"]
        compact["research"] = {
            "providers_merged": list(dict.fromkeys(
                item.get("provider") for item in attempts
                if item.get("capability") == "search" and item.get("outcome") in {"success", "partial"}
                and item.get("result_count", 0) > 0
            )),
        }
        # The current search contract may omit extraction receipts entirely.
        # An unknown page count must not look like zero extracted pages.
        if extraction_attempts:
            compact["research"]["pages_count"] = sum(
                item.get("result_count", 0) for item in extraction_attempts
                if item.get("outcome") in {"success", "partial"}
            )
        evidence = next((
            warning.get("details") for warning in projected.get("warnings") or []
            if isinstance(warning, dict) and warning.get("code") == "wsp.research.evidence"
        ), None)
        if isinstance(evidence, dict):
            # Share a small excerpt allowance across all pages; never duplicate
            # child observations or full text in the compact response.
            sources = evidence.get("sources") or []
            text_sources = sum(1 for source in sources if source.get("content"))
            allowance = 1200 // max(1, text_sources)  # UTF-8 bytes, across the batch
            excerpts = []
            truncated = bool(evidence.get("truncated"))
            for source in sources:
                excerpt = {key: source[key] for key in ("url", "error") if key in source}
                if source.get("content"):
                    encoded = source["content"].encode("utf-8")
                    excerpt["content"] = encoded[:allowance].decode("utf-8", errors="ignore")
                    truncated |= len(encoded) > allowance
                excerpts.append(excerpt)
            compact["research"].update({
                "pages_count": evidence.get("pages_count", 0),
                "failed_count": evidence.get("failed_count", 0),
                "sources": excerpts,
                "truncated": truncated,
                "content_trust": "untrusted_source_text",
            })
            if evidence.get("extraction_error"):
                compact["research"]["extraction_error"] = _short_message(evidence["extraction_error"])
    warnings = list(dict.fromkeys(
        message for item in projected.get("warnings") or []
        # The research evidence entry is the sources under "research", not a warning.
        if not (isinstance(item, dict) and item.get("code") == "wsp.research.evidence")
        and (message := _short_message(item))
    ))
    if warnings:
        compact["warnings"] = warnings
    if capability == "search":
        counts = dict(projected.get("metadata") or {})
        for warning in projected.get("warnings") or []:
            if isinstance(warning, dict) and warning.get("code") in {
                "wsp.search.redirects", "wsp.search.invalid_urls",
            }:
                counts.update(warning.get("details") or {})
        for key in (
            "redirects_wrapped", "redirects_resolved", "redirects_dropped",
            "invalid_urls_dropped",
        ):
            value = counts.get(key)
            if isinstance(value, int) and value > 0:
                compact[key] = value
    freshness = _freshness_from_v3_payload(projected)
    if freshness:
        compact["freshness"] = deepcopy(freshness)
    if projected.get("error"):
        compact["error"] = _short_message(projected["error"])
    if projected.get("status") == "failed":
        compact.setdefault("error", _short_message(projected.get("error_v3")) or "Web Search Plus request failed")
        reasons = []
        for attempt in [] if setup_error else attempts:
            empty = attempt.get("outcome") == "success" and attempt.get("result_count") == 0
            # A call cut off by the deadline (or lost by the engine) failed; one
            # cancelled because another provider or the research quorum won did not.
            end_reason = ((attempt.get("error") or {}).get("details") or {}).get("end_reason")
            cut_off = attempt.get("outcome") == "cancelled" and end_reason not in (
                "superseded_by_winner", "preempted_after_quorum")
            if attempt.get("outcome") in {"failed", "empty", "skipped"} or empty or cut_off:
                reason = _short_message(
                    attempt.get("error") or attempt.get("skip_reason")
                    or ("empty results" if empty else attempt.get("outcome"))
                )
                message = f"{attempt.get('provider')}: {reason}"
                if message not in reasons:
                    reasons.append(message)
        if reasons:
            compact["provider_errors"] = reasons
    return compact


_COMPACT_SNIPPET_CHARS = 1200


def _project_v3_payload(
    payload: dict[str, Any],
    *,
    capability: str,
    query: Optional[str] = None,
    urls: Optional[list[str]] = None,
    request_mode: Optional[str] = None,
    quality_report_requested: bool = False,
    recency_time_range: Optional[str] = None,
    recency_freshness: Optional[str] = None,
    detail: str = "full",
    requested_provider: Optional[str] = None,
) -> dict[str, Any]:
    """Preserve the additive 5.1.2 projection, then optionally compact it."""
    projected = {key: value for key, value in payload.items() if key not in {"results", "error"}}
    if capability == "extract" and isinstance(projected.get("observations"), list):
        # results[].content carries the bounded text; full observation text would
        # bypass max_context_chars (the untruncated page stays in stored_content).
        projected["observations"] = [
            {**item, "text": None} if isinstance(item, dict) else item
            for item in projected["observations"]
        ]
    receipt = payload.get("routing_receipt") or {}
    if capability == "search" and request_mode == "research":
        provider = "research"
    else:
        provider = receipt.get("selected_provider")
        if not provider:
            cache_origin = receipt.get("cache_origin") or {}
            if isinstance(cache_origin, dict):
                provider = cache_origin.get("selected_provider")
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

    failed_url_errors: dict[str, str] = {}
    if capability == "extract":
        for warning in payload.get("warnings") or []:
            details = warning.get("details") if isinstance(warning, dict) else None
            for failed in (details or {}).get("failed_urls") or []:
                if isinstance(failed, dict) and failed.get("url") and failed.get("error"):
                    failed_url_errors.setdefault(str(failed["url"]), str(failed["error"]))

    extract_limits = (payload.get("limits_applied") or {}).get("extract")
    if not isinstance(extract_limits, dict):
        extract_limits = {}
    result_items = [item for item in payload.get("results") or [] if isinstance(item, dict)]
    requested_urls: list[str] = []
    if capability == "extract":
        # The engine answers one result per processed URL, in request order.
        processed = extract_limits.get("processed_urls")
        if not isinstance(processed, list):
            processed = urls or []
        if len(processed) == len(result_items):
            requested_urls = [str(item) for item in processed]

    results = []
    for index, item in enumerate(result_items):
        url = _field_url(item.get("url"))
        result: dict[str, Any]
        if capability == "extract":
            result = {"url": url, "content": _field_text(item.get("text"))}
            if requested_urls:
                # `url` is where the provider ended up (redirects, canonical form).
                result["requested_url"] = requested_urls[index]
            observed = (item.get("url") or {}).get("observed") if isinstance(item.get("url"), dict) else url
            error_text = failed_url_errors.get(str(observed)) or failed_url_errors.get(str(url))
            if error_text and not result["content"]:
                result["error"] = error_text
            if isinstance(item.get("spans"), list):
                result["spans"] = [
                    dict(span) for span in item["spans"] if isinstance(span, dict)
                ]
                result["span_contract_version"] = item.get("span_contract_version")
        else:
            structured_snippet = item.get("snippet")
            result = {
                "title": _field_text(item.get("title")),
                "url": url,
                "snippet": _field_text(structured_snippet),
            }
            # Preserve additive, schema-validated v3.1 enrichment at the MCP
            # boundary.  Legacy title/url/snippet remain unchanged.
            snippet_provenance = (
                structured_snippet.get("provenance")
                if isinstance(structured_snippet, dict)
                else None
            )
            if (
                isinstance(snippet_provenance, dict)
                and snippet_provenance.get("aggregation") == "concat"
            ):
                result["snippet_aggregate"] = deepcopy(structured_snippet)
            for field in ("source_type", "fetch_priority"):
                if isinstance(item.get(field), dict):
                    result[field] = deepcopy(item[field])
        results.append(result)
    if capability == "extract" and not results and payload.get("status") == "failed" and failed_url_errors:
        # No URL could be read: one row per URL with its reason (page not
        # found, site refused, ...) instead of an empty list.
        results = [
            {"url": failed_url, "requested_url": failed_url, "content": "", "error": error_text}
            for failed_url, error_text in failed_url_errors.items()
        ]
    if capability == "extract":
        omitted = extract_limits.get("omitted_urls")
        if isinstance(omitted, list):
            # URLs past the per-call fan-out cap were not tried; say so per URL.
            message = f"not tried: limit of {extract_limits.get('max_urls')} URLs per call reached"
            results.extend(
                {"url": str(omitted_url), "requested_url": str(omitted_url), "content": "", "error": message}
                for omitted_url in omitted
            )
    projected["results"] = results
    if capability == "search" and quality_report_requested:
        projected["quality_report"] = _quality_report_from_v3(payload, projected)

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

    requested = recency_time_range or recency_freshness
    provider_name = projected.get("provider")
    existing_freshness = _freshness_from_v3_payload(payload) or _freshness_from_v3_payload(projected)
    if isinstance(existing_freshness, dict):
        projected.setdefault("metadata", {})["freshness"] = existing_freshness
    elif (
        capability == "search"
        and requested
        and isinstance(provider_name, str)
        and provider_name not in {"research", "exa"}
    ):
        from .providers import freshness_metadata

        projected.setdefault("metadata", {})["freshness"] = freshness_metadata(
            provider_name,
            requested,
        )
    if detail == "compact":
        return _compact_payload(
            projected, capability=capability, canonical=payload,
            requested_provider=requested_provider,
        )
    return projected


_search_engine: Any = None
_search_engine_failed = False
_search_engine_lock = threading.Lock()


def _load_search_engine() -> Any:
    """Import the bundled search engine once; None means use the subprocess path."""
    global _search_engine, _search_engine_failed
    if _search_engine is not None or _search_engine_failed:
        return _search_engine
    with _search_engine_lock:
        if _search_engine is None and not _search_engine_failed:
            try:
                from . import search as engine

                if not callable(getattr(engine, "run_cli_contract_v3", None)):
                    raise ImportError("search.run_cli_contract_v3 missing")
                _search_engine = engine
            except Exception as exc:  # pragma: no cover - broken installation
                # Importing the optional engine can execute arbitrary module or
                # host initialization code; retain the subprocess fallback.
                _search_engine_failed = True
                print(
                    json.dumps({"warning": f"in-process search engine unavailable, using subprocess: {exc}"}),
                    file=sys.stderr,
                )
    return _search_engine


_SUBPROCESS_ERRORS = {
    "failed": _typed_error_payload(
        code="wsp.subprocess.failed",
        message="Web Search Plus subprocess failed.",
        error_class="internal",
    ),
    "invalid_response": _typed_error_payload(
        code="wsp.subprocess.invalid_response",
        message="Web Search Plus subprocess returned an invalid response.",
        error_class="internal",
    ),
    "timeout": _typed_error_payload(
        code="wsp.subprocess.timeout",
        message="Web Search Plus subprocess timed out.",
        error_class="timeout",
        retryable=True,
    ),
}


async def _run_in_process(engine: Any, cmd: list[str], timeout: int) -> Optional[dict[str, Any]]:
    """Run ``search.py <argv>`` inside this process.

    Same argv, parser, config reload and v3 pipeline as the subprocess path,
    minus interpreter startup per call; it also lets http_client keep provider
    connections alive between calls. Error and timeout payloads match the
    subprocess path so clients see no difference. Returns None when the argv is
    outside the in-process scope, so the caller falls back to the subprocess.
    """
    argv = [str(part) for part in cmd[2:]]
    task = DaemonTask(engine.run_cli_contract_v3, argv)
    try:
        payload, _exit_code = await asyncio.to_thread(task.result, timeout)
    except (FuturesTimeoutError, asyncio.TimeoutError, TimeoutError):
        # Before 3.11 these are distinct classes, and asyncio re-raises the
        # future's timeout as asyncio.TimeoutError across to_thread.
        # The worker thread is a daemon bounded by per-provider HTTP timeouts.
        return deepcopy(_SUBPROCESS_ERRORS["timeout"])
    except ValueError as exc:
        if "only supports --contract-v3" in str(exc):
            return None
        print(json.dumps({"error": f"in-process search failed: {type(exc).__name__}"}), file=sys.stderr)
        return deepcopy(_SUBPROCESS_ERRORS["failed"])
    except SystemExit:
        # argparse rejected the argv; the CLI would exit 2 with usage on stderr.
        return deepcopy(_SUBPROCESS_ERRORS["failed"])
    except Exception as exc:
        # Engine/host failures have arbitrary exception types. Match the child
        # process's sanitized failure without disclosing exception text.
        print(json.dumps({"error": f"in-process search failed: {type(exc).__name__}"}), file=sys.stderr)
        return deepcopy(_SUBPROCESS_ERRORS["failed"])
    if not isinstance(payload, dict):
        return deepcopy(_SUBPROCESS_ERRORS["invalid_response"])
    # Round-trip through JSON so the result is exactly what the CLI would print.
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError):
        return deepcopy(_SUBPROCESS_ERRORS["invalid_response"])


async def _run_subprocess(cmd: list[str], timeout: int) -> dict[str, Any]:
    # search.py has package-relative imports, so run it as a module. Put this
    # checkout first on PYTHONPATH, including when it has not been installed.
    argv = cmd
    env = os.environ.copy()
    if len(cmd) >= 2 and cmd[1] == str(SEARCH_SCRIPT):
        package_parent = str(SEARCH_SCRIPT.parent.parent)
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_parent, env.get("PYTHONPATH")]))
        argv = [cmd[0], "-m", f"{__package__ or SEARCH_SCRIPT.parent.name}.search", *cmd[2:]]
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            argv,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return deepcopy(_SUBPROCESS_ERRORS["timeout"])
    raw = (result.stdout if result.returncode == 0 else result.stderr).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return deepcopy(_SUBPROCESS_ERRORS["invalid_response" if result.returncode == 0 else "failed"])


async def _run_cmd(
    cmd: list[str],
    timeout: int,
    *,
    capability: str,
    query: Optional[str] = None,
    urls: Optional[list[str]] = None,
    request_mode: Optional[str] = None,
    quality_report_requested: bool = False,
    recency_time_range: Optional[str] = None,
    recency_freshness: Optional[str] = None,
    detail: str = "full",
    requested_provider: Optional[str] = None,
) -> list[TextContent]:
    payload = None
    force_subprocess = os.environ.get("WSP_FORCE_SUBPROCESS", "").strip().lower() in {"1", "true", "yes", "on"}
    engine = None if force_subprocess else _load_search_engine()
    if engine is not None:
        payload = await _run_in_process(engine, cmd, timeout)
    if payload is None:
        payload = await _run_subprocess(cmd, timeout)
    if isinstance(payload, dict) and payload.get("contract_version") == "3.0":
        payload = _project_v3_payload(
            payload,
            capability=capability,
            query=query,
            urls=urls,
            request_mode=request_mode,
            quality_report_requested=quality_report_requested,
            recency_time_range=recency_time_range,
            recency_freshness=recency_freshness,
            detail=detail,
            requested_provider=requested_provider,
        )
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    detail = _resolve_detail(arguments)
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
            if detail == "compact":
                payload = _compact_payload(payload, capability="search")
            return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
        for label in ("include_domains", "exclude_domains"):
            problem = _unsafe_variadic_values(label, arguments.get(label))
            if problem:
                return _invalid_arguments_payload(problem, detail=detail)
        cmd = [
            sys.executable,
            str(SEARCH_SCRIPT),
            f"--query={query}",
            "--provider",
            provider,
            "--compact",
            "--contract-v3",
        ]
        # Omitted or null count leaves --max-results to search.py, which reads
        # defaults.max_results from config.json. An explicit count wins.
        _append_optional(cmd, "--max-results", arguments.get("count"))
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
        quality_report_requested = _as_bool(arguments.get("quality_report", False))
        if quality_report_requested:
            cmd.append("--quality-report")
        if _as_bool(arguments.get("no_cache", False)):
            cmd.append("--no-cache")
        _append_optional(cmd, "--cache-ttl", arguments.get("cache_ttl"))
        timeout = DEFAULT_SEARCH_SUBPROCESS_TIMEOUT_SECONDS
        if _donsetch_outer_budget_applies(provider):
            timeout = DEFAULT_DONSETCH_SUBPROCESS_TIMEOUT_SECONDS
        elif mode == "research":
            # Direct Python callers can bypass the MCP schema; retain the
            # historical default/clamp for their outer process budget.
            try:
                budget = float(research_time_budget)
            except (TypeError, ValueError):
                budget = 55.0
            if not math.isfinite(budget):
                budget = 55.0
            timeout = math.ceil(min(75.0, max(1.0, budget))) + RESEARCH_SUBPROCESS_GRACE_SECONDS
        return await _run_cmd(
            cmd,
            timeout=timeout,
            capability="search",
            query=query,
            request_mode=mode,
            quality_report_requested=quality_report_requested,
            recency_time_range=arguments.get("time_range"),
            recency_freshness=arguments.get("freshness"),
            detail=detail,
            requested_provider=provider,
        )

    if name == "web_extract":
        urls = arguments["urls"]
        if isinstance(urls, str):
            urls = [urls]
        problem = _unsafe_variadic_values("urls", urls)
        if problem or not urls:
            return _invalid_arguments_payload(problem or "Invalid urls: at least one URL is required", detail=detail)
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
        if arguments.get("spans_query") is not None:
            cmd.append(f"--spans-query={arguments['spans_query']}")
        provider = _canonical_provider(arguments.get("provider", "auto"))
        timeout = (
            DEFAULT_DONSETCH_SUBPROCESS_TIMEOUT_SECONDS * max(1, len(urls))
            if _donsetch_outer_budget_applies(provider)
            else 90
        )
        return await _run_cmd(
            cmd, timeout=timeout, capability="extract", urls=urls,
            detail=detail, requested_provider=provider,
        )

    raise ValueError(f"Unknown tool: {name}")


async def _mcp_list_tools(
    _ctx: ServerRequestContext[Any], _params: PaginatedRequestParams | None
) -> ListToolsResult:
    """Adapt the stable tool definitions to the MCP SDK v2 low-level boundary."""
    return ListToolsResult(tools=await list_tools())


async def _mcp_call_tool(
    _ctx: ServerRequestContext[Any], params: CallToolRequestParams
) -> CallToolResult:
    """Validate and adapt one tool call to the MCP SDK v2 result contract."""
    tools = {tool.name: tool for tool in await list_tools()}
    tool = tools.get(params.name)
    if tool is None:
        raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")

    arguments = params.arguments or {}
    validation_error = next(
        Draft202012Validator(tool.input_schema).iter_errors(arguments), None
    )
    if validation_error is not None:
        # Describe the schema location without reflecting caller values.
        location = ".".join(str(part) for part in validation_error.absolute_path) or "$"
        raise MCPError(
            INVALID_PARAMS,
            f"Invalid arguments for tool '{params.name}' "
            f"({validation_error.validator} validation failed at {location}).",
        )

    try:
        content = await call_tool(params.name, arguments)
    except Exception:
        # A user-facing MCP hook must return the sanitized wire error for any
        # engine/host failure; no narrower class covers those external hooks.
        payload = _typed_error_payload(
            code="wsp.mcp.tool_execution_failed",
            message="Web Search Plus tool execution failed.",
            error_class="internal",
        )
        # Arguments passed schema validation; environment and config defaults
        # are normalized by _resolve_detail at their own boundaries.
        detail = _resolve_detail(arguments)
        if detail == "compact":
            payload = _compact_payload(payload, capability="search")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
            is_error=True,
        )
    is_error = False
    for item in content:
        try:
            payload = json.loads(getattr(item, "text", "") or "")
        except (TypeError, ValueError):
            # Hooks may return non-JSON content. ValueError also covers the
            # decoder's integer-length limit, not only JSONDecodeError.
            continue
        if isinstance(payload, dict) and payload.get("status") == "failed":
            is_error = True
            break
    return CallToolResult(content=content, is_error=is_error)


app = Server(
    "web-search-plus",
    version=__version__,
    on_list_tools=_mcp_list_tools,
    on_call_tool=_mcp_call_tool,
)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def _status_payload() -> dict[str, Any]:
    from . import readiness
    from .config import read_runtime_config

    behavior_config, config_warning = _load_behavior_config()
    # What the engine runs with (profile effects, its own validation) rather
    # than this server's reading of the file: they differed for self_hosted.
    path = runtime_config_path()
    engine_config, engine_error = read_runtime_config(path)
    if engine_error:
        config_warning = f"Invalid config: the next search moves {path} aside and uses the defaults: {engine_error}"
    report = readiness.evaluate(engine_config, list(SEARCH_PROVIDERS))
    configured = {name: bool(report[name].accepted) for name in SEARCH_PROVIDERS}
    payload = {
        "version": __version__,
        "server": "web-search-plus-mcp",
        "search_configured": any(ok for name, ok in configured.items() if "search" in SEARCH_PROVIDERS[name]["capabilities"]),
        # Set up is not enough for a search without provider="X": an
        # explicit-only or disabled provider never runs automatically.
        "search_auto_ready": any(
            report[name].state is readiness.Readiness.READY
            for name in SEARCH_PROVIDERS if "search" in SEARCH_PROVIDERS[name]["capabilities"]
        ),
        "extract_configured": any(configured.get(provider) for provider in EXTRACT_PROVIDERS),
        "tools_if_started_now": ["web_search", "web_extract"],
        "config_path": str(runtime_config_path()),
        "routing_preferences": engine_config["auto_routing"],
        # The engine pins the top-level key; defaults.provider is its source.
        "default_provider": engine_config.get("default_provider") or engine_config["defaults"]["provider"],
        "providers": {
            name: {
                "env": SEARCH_PROVIDERS[name]["env"], "configured": ok, "capabilities": SEARCH_PROVIDERS[name]["capabilities"],
                **{key: value for key, value in report[name].to_public().items() if key != "provider"},
            }
            for name, ok in configured.items()
        },
    }
    if config_warning:
        payload["config_warning"] = config_warning
    spec = PROVIDER_SPECS.get("donsetch")
    inspect = getattr(getattr(spec, "execute_search", None), "__globals__", {}).get(
        "inspect_donsetch_readiness"
    )
    if callable(inspect):
        payload["donsetch"] = inspect(
            key=os.environ.get("DONSETCH_BIN"),
            config=behavior_config,
        )
    payload["jev"] = jev_setup.status_payload(os.environ, behavior_config)
    return payload


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
    setup.add_argument("--config-path", help=f"Override config path instead of {CONFIG_ENV_VAR}/default")
    jev = setup.add_mutually_exclusive_group()
    jev.add_argument("--jev", action="store_true", help="Enable optional Jev. Default off.")
    jev.add_argument("--no-jev", action="store_true", help="Leave optional Jev disabled (default).")
    setup.add_argument(
        "--jev-decisions",
        help="Comma-separated Jev decisions: search_type,extract_quality,language_fill",
    )
    setup.add_argument("--jev-key-file", help="Path written as TYPESAFE_API_KEY_FILE (never paste the key on the CLI)")
    config_p = sub.add_parser("config", help="Inspect or change routing preferences in config.json")
    config_p.add_argument("--config-path", help=f"Override config path instead of {CONFIG_ENV_VAR}/default")
    config_sub = config_p.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Show current routing preferences")
    set_default = config_sub.add_parser("set-default", help="Use one provider strictly when auto-routing is off")
    set_default.add_argument("provider")
    set_routing = config_sub.add_parser("set-routing", help="Turn auto-routing on or off")
    set_routing.add_argument("state", choices=["on", "off"])
    set_priority = config_sub.add_parser("set-priority", help="Set comma-separated search provider priority and use custom order")
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
    set_threshold = config_sub.add_parser("set-threshold", help="Store legacy confidence threshold from 0 to 1 (no effect since 5.0)")
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
            if payload.get("config_warning"):
                print(f"Warning: {payload['config_warning']}")
            print(f"Search configured: {'yes' if payload['search_configured'] else 'no'}")
            if payload["search_configured"] and not payload["search_auto_ready"]:
                print("Automatic search: no provider may run without provider=\"name\" (marked ~ below)")
            print(f"Extraction configured: {'yes' if payload['extract_configured'] else 'no'}")
            for name, meta in payload["providers"].items():
                mark = "✓" if meta["state"] == "ready" else "~" if meta["configured"] else "·"
                note = f" — {meta['reason']} Fix: {'; '.join(meta.get('fix', []))}" if mark == "~" else ""
                print(f"  {mark} {name}: {meta['env']} ({', '.join(meta['capabilities'])}){note}")
            donsetch = payload.get("donsetch") or {}
            if donsetch.get("binary_configured") or donsetch.get("state") not in {None, "missing"}:
                print(
                    "DonSeTch binary: "
                    f"state={donsetch.get('state')}, "
                    f"version={donsetch.get('version') or 'unknown'}, "
                    f"compatibility={donsetch.get('compatibility')}, "
                    f"tested={donsetch.get('tested_version')}"
                )
            jev = payload.get("jev") or {}
            on = "on" if jev.get("enabled") else "off"
            key = "yes" if jev.get("key_present") else "no"
            chosen = [name for name, flag in (jev.get("decisions") or {}).items() if flag]
            print(f"Jev: {on}, key={key}, decisions={', '.join(chosen) or 'none'}")
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
        path = Path(args.env_file).expanduser().resolve()
        if args.config_path:
            os.environ[CONFIG_ENV_VAR] = args.config_path
        want_jev = args.jev
        try:
            jev_decisions = jev_setup.parse_decisions(args.jev_decisions)
        except ValueError as exc:
            raise SystemExit(str(exc))
        jev_key_file = args.jev_key_file
        extra_keys: list[str] = []
        extra_values: dict[str, str] = {}
        if want_jev:
            if jev_key_file:
                extra_keys.append(jev_setup.JEV_ENV_FILE)
                extra_values[jev_setup.JEV_ENV_FILE] = str(Path(jev_key_file).expanduser())
            else:
                extra_keys.append(jev_setup.JEV_ENV)
        keys = list(PRESETS[args.preset]) + extra_keys
        candidates = [p.expanduser().resolve() for p in candidate_env_paths(__file__)]
        note = (
            f"The server reads {path} at startup."
            if path in candidates else
            f"{path} is a template only and is not automatically read by this server. "
            "Copy its keys into the MCP client's env block or a server env file."
        )
        note += " Server env files, in precedence order: " + ", ".join(map(str, candidates)) + ". Existing process environment wins. Restart after changes."
        snippet_env = {
            "LINKUP_API_KEY": "your_linkup_key",
            "TAVILY_API_KEY": "your_tavily_key",
            "BRAVE_API_KEY": "your_brave_key",
        }
        if want_jev:
            if jev_key_file:
                snippet_env["TYPESAFE_API_KEY_FILE"] = jev_key_file
            else:
                snippet_env["TYPESAFE_API_KEY"] = "your_typesafe_key"
        payload = {
            "preset": args.preset,
            "env_file": str(path),
            "server_env_files": list(map(str, candidates)),
            "env_file_auto_loaded": path in candidates,
            "keys": keys,
            "snippet": {
                "mcpServers": {
                    "web-search-plus": {
                        "command": "uvx",
                        "args": ["web-search-plus-mcp"],
                        "env": snippet_env,
                    }
                },
                "note": note,
            },
            "jev": {
                "enabled": want_jev,
                "decisions": list(jev_decisions) if want_jev else [],
                "key_env": extra_keys[0] if extra_keys else None,
            },
        }
        if not args.dry_run:
            if path.exists() and not args.force:
                raise SystemExit(f"Refusing to overwrite existing {path}. Pass --force to replace it.")
            lines = ["# web-search-plus-mcp provider config"]
            lines.extend(f"{key}={extra_values.get(key, '')}" for key in keys)
            path.write_text("\n".join(lines) + "\n")
            if want_jev:
                config = _read_config_for_edit(runtime_config_path())
                jev_setup.apply_jev_config(config, enabled=True, decisions=jev_decisions)
                written = _write_cli_config(config, runtime_config_path())
                payload["config_path"] = str(written)
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            action = "Would write" if args.dry_run else "Wrote"
            print(f"{action} {path} with preset {args.preset}: {', '.join(keys)}")
            print("\n".join(jev_setup.plan_lines(
                want_enable=want_jev,
                decisions=jev_decisions,
                has_key=bool(jev_key_file) or jev_setup.key_present(os.environ),
            )))
            print("\nCanonical MCP stdio snippet:")
            print(json.dumps(payload["snippet"], indent=2))
        return 0
    if args.command == "config":
        if args.config_path:
            os.environ[CONFIG_ENV_VAR] = args.config_path
        path = runtime_config_path()
        if args.config_command == "show":
            from .config import read_runtime_config

            _config, warning = _load_behavior_config(path)
            # The engine's view, as in status.
            config, engine_error = read_runtime_config(path)
            if engine_error:
                warning = f"Invalid config: the next search moves {path} aside and uses the defaults: {engine_error}"
            payload = {"config_path": str(path),
                       "default_provider": config.get("default_provider") or config["defaults"]["provider"],
                       "routing_preferences": config["auto_routing"]}
            if warning:
                payload["warning"] = warning
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        if args.config_command == "reset":
            if not args.yes:
                raise SystemExit("Refusing to reset without --yes")
            _write_cli_config(_default_behavior_config(), path, backup=True)
            print(f"Reset routing preferences in {path}")
            return 0
        config = _read_config_for_edit(path)
        if args.config_command == "set-default":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config["defaults"]["provider"] = provider
            config["default_provider"] = provider
            config["auto_routing"]["enabled"] = False
        elif args.config_command == "set-routing":
            config["auto_routing"]["enabled"] = args.state == "on"
        elif args.config_command == "set-priority":
            config["auto_routing"]["provider_priority"] = _normalize_provider_list(args.providers, allow_empty=False)
            config["auto_routing"]["order"] = "custom"
        elif args.config_command == "set-extract-priority":
            config["auto_routing"]["extract_provider_priority"] = _normalize_extract_provider_list(args.providers)
        elif args.config_command == "set-fallback":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config["auto_routing"]["fallback_provider"] = provider
        elif args.config_command in {"disable", "disable-provider"}:
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            disabled = config["auto_routing"]["disabled_providers"]
            if provider not in disabled:
                disabled.append(provider)
            config["auto_routing"]["disabled_providers"] = disabled
        elif args.config_command in {"enable", "enable-provider"}:
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            disabled = config["auto_routing"]["disabled_providers"]
            config["auto_routing"]["disabled_providers"] = [p for p in disabled if p != provider]
        elif args.config_command == "set-auto-allow":
            provider = _canonical_provider(args.provider)
            if provider not in SEARCH_PROVIDERS:
                raise SystemExit(f"Unknown provider: {args.provider}")
            config["auto_routing"]["auto_allow"][
                provider
            ] = args.state == "on"
        elif args.config_command == "set-threshold":
            config["auto_routing"]["confidence_threshold"] = args.threshold
        _write_cli_config(config, path)
        if args.config_command == "set-threshold":
            print("confidence_threshold is stored for compatibility; no effect since 5.0.", file=sys.stderr)
        updated, _ = _load_behavior_config(path)
        print(json.dumps({"config_path": str(path), "default_provider": updated["defaults"]["provider"], "routing_preferences": updated["auto_routing"]}, indent=2, ensure_ascii=False))
        return 0
    parser.error("unknown command")
    return 2


def run():
    asyncio.run(main())


if __name__ == "__main__":
    raise SystemExit(cli_main())
