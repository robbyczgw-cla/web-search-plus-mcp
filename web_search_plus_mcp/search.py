#!/usr/bin/env python3
"""
Web Search Plus — Unified Multi-Provider Search and Extraction with Intelligent Auto-Routing
Version: 2.2.0-mcp
Supports search providers: You.com, Serper, Exa, Firecrawl, Tavily, Linkup,
Brave Search, SerpBase, Querit, Parallel, Perplexity, Kilo Perplexity, SearXNG.
Supports extract providers: Firecrawl, Linkup, Parallel, Tavily, Exa, You.com.

Smart Routing uses multi-signal analysis:
  - Routing v2 language/script and query-class detection
  - Query intent classification (shopping, research, discovery)
  - Linguistic pattern detection (how much vs how does)
  - Product/brand recognition
  - URL detection
  - Confidence scoring

Usage:
    python3 search.py --query "..."                    # Auto-route based on query
    python3 search.py --provider [you|serper|exa|firecrawl|tavily|linkup|brave|serpbase|querit|perplexity|kilo-perplexity|searxng|auto] --query "..." [options]

Examples:
    python3 search.py -q "東京 AI ニュース 今日"              # → You.com (multilingual current)
    python3 search.py -q "arXiv 2024 LLM scaling laws"      # → Exa (academic discovery)
    python3 search.py -q "latest OpenSSH CVE mitigation"    # → Serper (security/current)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from urllib.request import Request, urlopen

ROUTING_POLICY = "routing-v2"
CONFIG_ENV_VAR = "WEB_SEARCH_PLUS_CONFIG"

# Keep direct script/importlib.spec execution working for compatibility tests.
_MODULE_DIR = Path(__file__).resolve().parent
if __package__ in (None, "") and str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

try:  # pragma: no cover - import style depends on CLI/package execution
    from .cache import (
        CACHE_DIR,
        DEFAULT_CACHE_TTL,
        PROVIDER_HEALTH_FILE,
        _build_cache_payload,
        _ensure_cache_dir,
        _get_cache_key,
        _get_cache_path,
        cache_clear,
        cache_get,
        cache_put,
        cache_stats,
    )
    from .config import (
        DEFAULT_CONFIG,
        ProviderConfigError,
        _append_missing_default_providers,
        _canonical_provider,
        _deepcopy_default_config,
        _load_env_file,
        _normalize_routing_provider_config,
        _normalize_routing_provider_list_config,
        _quarantine_runtime_config,
        _unique_timestamped_path,
        _validate_runtime_config,
        _validate_searxng_url,
        _VALID_PROVIDERS,
        get_api_key,
        get_env_key,
        get_searxng_instance_url,
        load_config,
        validate_api_key,
    )
except ImportError:  # pragma: no cover
    from cache import (  # type: ignore
        CACHE_DIR,
        DEFAULT_CACHE_TTL,
        PROVIDER_HEALTH_FILE,
        _build_cache_payload,
        _ensure_cache_dir,
        _get_cache_key,
        _get_cache_path,
        cache_clear,
        cache_get,
        cache_put,
        cache_stats,
    )
    from config import (  # type: ignore
        DEFAULT_CONFIG,
        ProviderConfigError,
        _append_missing_default_providers,
        _canonical_provider,
        _deepcopy_default_config,
        _load_env_file,
        _normalize_routing_provider_config,
        _normalize_routing_provider_list_config,
        _quarantine_runtime_config,
        _unique_timestamped_path,
        _validate_runtime_config,
        _validate_searxng_url,
        _VALID_PROVIDERS,
        get_api_key,
        get_env_key,
        get_searxng_instance_url,
        load_config,
        validate_api_key,
    )

try:  # pragma: no cover - import style depends on CLI/package execution
    from . import http_client as _http_client
    from .http_client import (
        ProviderRequestError,
        TRANSIENT_HTTP_CODES,
        execute_provider_with_retry,
        _read_json_response,
        _read_response_body,
    )
except ImportError:  # pragma: no cover
    import http_client as _http_client  # type: ignore
    from http_client import (  # type: ignore
        ProviderRequestError,
        TRANSIENT_HTTP_CODES,
        execute_provider_with_retry,
        _read_json_response,
        _read_response_body,
    )


def make_request(url: str, headers: dict, body: dict, timeout: int = 30) -> dict:
    """Compatibility wrapper around http_client.make_request."""
    _http_client.urlopen = urlopen
    return _http_client.make_request(url, headers, body, timeout)


def make_get_request(url: str, headers: dict, timeout: int = 30) -> dict:
    """Compatibility wrapper around http_client.make_get_request."""
    _http_client.urlopen = urlopen
    return _http_client.make_get_request(url, headers, timeout)

__all__ = [
    "CACHE_DIR",
    "DEFAULT_CACHE_TTL",
    "PROVIDER_HEALTH_FILE",
    "_build_cache_payload",
    "_ensure_cache_dir",
    "_get_cache_key",
    "_get_cache_path",
    "cache_clear",
    "cache_get",
    "cache_put",
    "cache_stats",
    "DEFAULT_CONFIG",
    "ProviderConfigError",
    "_append_missing_default_providers",
    "_canonical_provider",
    "_deepcopy_default_config",
    "_load_env_file",
    "_normalize_routing_provider_config",
    "_normalize_routing_provider_list_config",
    "_quarantine_runtime_config",
    "_unique_timestamped_path",
    "_validate_runtime_config",
    "_validate_searxng_url",
    "_VALID_PROVIDERS",
    "get_api_key",
    "get_env_key",
    "get_searxng_instance_url",
    "load_config",
    "validate_api_key",
    "ProviderRequestError",
    "TRANSIENT_HTTP_CODES",
    "execute_provider_with_retry",
    "_read_json_response",
    "_read_response_body",
    "make_get_request",
    "make_request",
    "QueryAnalyzer",
    "_choose_tie_winner",
    "_provider_auto_allowed",
    "auto_route_provider",
    "explain_routing",
]
# Routing helpers live in routing.py and are imported below for compatibility.
try:  # pragma: no cover - import style depends on CLI/package execution
    from . import routing as _routing
    from .routing import ROUTING_POLICY, _choose_tie_winner, _provider_auto_allowed
except ImportError:  # pragma: no cover
    import routing as _routing  # type: ignore
    from routing import ROUTING_POLICY, _choose_tie_winner, _provider_auto_allowed  # type: ignore

try:  # pragma: no cover - import style depends on CLI/package execution
    from . import extract as _extract
    from .providers import core as _core_provider
    from .providers import parallel as _parallel_provider
    from .providers import perplexity as _perplexity_provider
    from .provider_health import (
        COOLDOWN_STEPS_SECONDS,
        RETRY_BACKOFF_SECONDS,
        _ensure_parent,
        _load_provider_health,
        _save_provider_health,
        mark_provider_failure,
        provider_in_cooldown,
        reset_provider_health,
    )
    from .quality import (
        CANONICAL_DOMAIN_RULES,
        _domain_matches_rule,
        _result_domain,
        _snippet_text,
        _title_from_url,
        build_quality_report,
        deduplicate_results_across_providers,
        normalize_result_url,
        rerank_results_for_intent,
        select_research_providers,
    )
    from .research import run_research_mode
except ImportError:  # pragma: no cover
    import extract as _extract  # type: ignore
    from providers import core as _core_provider  # type: ignore
    from providers import parallel as _parallel_provider  # type: ignore
    from providers import perplexity as _perplexity_provider  # type: ignore
    from provider_health import (  # type: ignore
        COOLDOWN_STEPS_SECONDS,
        RETRY_BACKOFF_SECONDS,
        _ensure_parent,
        _load_provider_health,
        _save_provider_health,
        mark_provider_failure,
        provider_in_cooldown,
        reset_provider_health,
    )
    from quality import (  # type: ignore
        CANONICAL_DOMAIN_RULES,
        _domain_matches_rule,
        _result_domain,
        _snippet_text,
        _title_from_url,
        build_quality_report,
        deduplicate_results_across_providers,
        normalize_result_url,
        rerank_results_for_intent,
        select_research_providers,
    )
    from research import run_research_mode  # type: ignore

_COMPAT_REEXPORTS = (
    COOLDOWN_STEPS_SECONDS,
    RETRY_BACKOFF_SECONDS,
    _ensure_parent,
    _load_provider_health,
    _save_provider_health,
    CANONICAL_DOMAIN_RULES,
    _domain_matches_rule,
    _result_domain,
    _snippet_text,
    normalize_result_url,
)


class QueryAnalyzer(_routing.QueryAnalyzer):
    """Compatibility wrapper that respects monkeypatches to search.get_api_key."""

    def __init__(self, config: Dict[str, Any]):
        original_get_api_key = _routing.get_api_key
        try:
            _routing.get_api_key = get_api_key
            super().__init__(config)
        finally:
            _routing.get_api_key = original_get_api_key

    def route(self, query: str) -> Dict[str, Any]:
        original_get_api_key = _routing.get_api_key
        try:
            _routing.get_api_key = get_api_key
            return super().route(query)
        finally:
            _routing.get_api_key = original_get_api_key


def auto_route_provider(query: str, config: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("auto_routing", {}).get("enabled", True):
        provider = config.get("default_provider") or config.get("defaults", {}).get("provider", "serper")
        return {
            "provider": provider,
            "confidence": 1.0,
            "confidence_level": "high",
            "reason": "auto_routing_disabled_default_provider",
            "routing_policy": ROUTING_POLICY,
            "scores": {},
            "top_signals": [],
            "auto_routed": False,
        }
    return QueryAnalyzer(config).route(query)


def explain_routing(query: str, config: Dict[str, Any]) -> Dict[str, Any]:
    original_get_api_key = _routing.get_api_key
    try:
        _routing.get_api_key = get_api_key
        return _routing.explain_routing(query, config)
    finally:
        _routing.get_api_key = original_get_api_key

# Provider health, result-quality, and research-mode helpers live in dedicated
# modules and are imported above for backward-compatible access through search.py.


def _sync_core_provider_dependencies() -> None:
    """Keep provider modules compatible with search.py monkeypatches."""
    _core_provider.make_request = make_request
    _core_provider.make_get_request = make_get_request
    _core_provider.urlopen = urlopen
    _core_provider.Request = Request
    _core_provider._read_json_response = _read_json_response
    _core_provider._read_response_body = _read_response_body
    _core_provider._title_from_url = _title_from_url


def _sync_extract_dependencies() -> None:
    """Keep extract orchestration compatible with search.py monkeypatches."""
    _extract.get_api_key = get_api_key
    _extract.load_config = load_config
    _extract.provider_in_cooldown = provider_in_cooldown
    _extract.mark_provider_failure = mark_provider_failure
    _extract.reset_provider_health = reset_provider_health
    _extract.execute_provider_with_retry = execute_provider_with_retry
    _extract.extract_firecrawl = extract_firecrawl
    _extract.extract_linkup = extract_linkup
    _extract.extract_tavily = extract_tavily
    _extract.extract_exa = extract_exa
    _extract.extract_you = extract_you
    _extract.extract_parallel = extract_parallel


# =============================================================================
# HTTP request helpers live in http_client.py and are imported above for compatibility.

# =============================================================================
# Serper (Google Search API)
# =============================================================================

def search_serper(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_serper(*args, **kwargs)


def _strip_tracking_params(*args, **kwargs):
    _sync_core_provider_dependencies()
    return _core_provider._strip_tracking_params(*args, **kwargs)


def _serpbase_related_search_query(*args, **kwargs):
    _sync_core_provider_dependencies()
    return _core_provider._serpbase_related_search_query(*args, **kwargs)


def search_serpbase(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_serpbase(*args, **kwargs)


def search_brave(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_brave(*args, **kwargs)


def search_tavily(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_tavily(*args, **kwargs)


def _map_querit_time_range(*args, **kwargs):
    return _core_provider._map_querit_time_range(*args, **kwargs)


def search_querit(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_querit(*args, **kwargs)


def search_linkup(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_linkup(*args, **kwargs)


def _map_firecrawl_time_range(*args, **kwargs):
    return _core_provider._map_firecrawl_time_range(*args, **kwargs)


def search_firecrawl(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_firecrawl(*args, **kwargs)


def _normalize_extract_result(*args, **kwargs):
    _sync_core_provider_dependencies()
    return _core_provider._normalize_extract_result(*args, **kwargs)


def extract_firecrawl(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.extract_firecrawl(*args, **kwargs)


def extract_linkup(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.extract_linkup(*args, **kwargs)


def extract_tavily(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.extract_tavily(*args, **kwargs)


def extract_exa(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.extract_exa(*args, **kwargs)


def extract_you(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.extract_you(*args, **kwargs)


def _patch_parallel_provider() -> None:
    _parallel_provider.make_request = make_request
    _parallel_provider._title_from_url = _title_from_url
    _parallel_provider._normalize_extract_result = _normalize_extract_result


def extract_parallel(
    urls: List[str],
    api_key: str,
    output_format: str = "markdown",
    include_images: bool = False,
    include_raw_html: bool = False,
    render_js: bool = False,
    api_url: str = "https://api.parallel.ai/v1/extract",
    timeout: int = 60,
    client_model: Optional[str] = None,
    max_chars_total: int = 12000,
    max_chars_per_result: int = 6000,
) -> dict:
    """Compatibility wrapper for the Parallel extraction adapter."""
    _patch_parallel_provider()
    return _parallel_provider.extract_parallel(
        urls,
        api_key,
        output_format=output_format,
        include_images=include_images,
        include_raw_html=include_raw_html,
        render_js=render_js,
        api_url=api_url,
        timeout=timeout,
        client_model=client_model,
        max_chars_total=max_chars_total,
        max_chars_per_result=max_chars_per_result,
    )


EXTRACT_PROVIDER_PRIORITY = _extract.EXTRACT_PROVIDER_PRIORITY


def extract_plus(*args, **kwargs) -> dict:
    _sync_extract_dependencies()
    return _extract.extract_plus(*args, **kwargs)


# =============================================================================
# Exa (Neural/Semantic/Deep Search)
# =============================================================================

def search_exa(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_exa(*args, **kwargs)


# =============================================================================
# Parallel (LLM-ready web search)
# =============================================================================

def search_parallel(
    query: str,
    api_key: str,
    max_results: int = 5,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    api_url: str = "https://api.parallel.ai/v1/search",
    timeout: int = 45,
    client_model: Optional[str] = None,
) -> dict:
    """Compatibility wrapper for the Parallel search adapter."""
    _patch_parallel_provider()
    return _parallel_provider.search_parallel(
        query,
        api_key,
        max_results=max_results,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        api_url=api_url,
        timeout=timeout,
        client_model=client_model,
    )


# =============================================================================
# Perplexity-compatible Direct Answers
# =============================================================================

def search_perplexity(
    query: str,
    api_key: str,
    max_results: int = 5,
    model: str = "sonar-pro",
    api_url: str = "https://api.perplexity.ai/chat/completions",
    freshness: Optional[str] = None,
    provider_name: str = "perplexity",
) -> dict:
    """Compatibility wrapper for the Perplexity-compatible adapter."""
    _perplexity_provider.make_request = make_request
    _perplexity_provider._title_from_url = _title_from_url
    return _perplexity_provider.search_perplexity(
        query,
        api_key,
        max_results=max_results,
        model=model,
        api_url=api_url,
        freshness=freshness,
        provider_name=provider_name,
    )


# =============================================================================
# You.com (LLM-Ready Web & News Search)
# =============================================================================

def search_you(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_you(*args, **kwargs)


def search_searxng(*args, **kwargs) -> dict:
    _sync_core_provider_dependencies()
    return _core_provider.search_searxng(*args, **kwargs)


def main():
    config = load_config()
    
    parser = argparse.ArgumentParser(
        description="Web Search Plus — Intelligent multi-provider search with smart auto-routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Intelligent Auto-Routing:
  The query is analyzed using multi-signal detection to find the optimal provider:
  
  Shopping Intent → Serper (Google)
    "how much", "price of", "buy", product+brand combos, deals, specs
  
  Research Intent → Tavily  
    "how does", "explain", "what is", analysis, pros/cons, tutorials

  Multilingual + Real-Time AI Search → Querit
    multilingual search, metadata-rich results, current information for AI workflows
  
  Discovery Intent → Exa (Neural)
    "similar to", "companies like", "alternatives", URLs, startups, papers

  Direct Answer Intent → Perplexity (via Kilo Gateway)
    "what is", "current status", local events, synthesized up-to-date answers

Examples:
  python3 search.py -q "iPhone 16 Pro Max price"          # → Serper (shopping)
  python3 search.py -q "how does HTTPS encryption work"   # → Tavily (research)
  python3 search.py -q "startups similar to Notion"       # → Exa (discovery)
  python3 search.py --explain-routing -q "your query"     # Debug routing

Full docs: See README.md and SKILL.md
        """,
    )
    
    # Common arguments
    parser.add_argument(
        "--provider", "-p", 
        choices=["serper", "serpbase", "brave", "tavily", "linkup", "querit", "exa", "firecrawl", "parallel", "perplexity", "kilo-perplexity", "you", "searxng", "auto"],
        help="Search provider (auto=intelligent routing)"
    )
    parser.add_argument(
        "--query", "-q", 
        help="Search query"
    )
    parser.add_argument(
        "--extract-urls",
        nargs="*",
        help="Extract content from one or more URLs instead of running a search"
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default="markdown",
        choices=["markdown", "html"],
        help="Extraction output format"
    )
    parser.add_argument("--extract-images", action="store_true", help="Extract image metadata when supported")
    parser.add_argument("--include-raw-html", action="store_true", help="Include raw HTML when supported")
    parser.add_argument("--render-js", action="store_true", help="Render JavaScript before extraction when supported")
    parser.add_argument(
        "--max-results", "-n", 
        type=int, 
        default=config.get("defaults", {}).get("max_results", 5),
        help="Maximum results (default: 5)"
    )
    parser.add_argument(
        "--images", 
        action="store_true",
        help="Include images (Serper/Tavily)"
    )
    
    # Auto-routing options
    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="Use intelligent auto-routing (default when no provider specified)"
    )
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow explicit --provider calls to fall back to other configured providers on failure. Auto-routing already uses fallback."
    )
    parser.add_argument(
        "--explain-routing",
        action="store_true",
        help="Show detailed routing analysis (debug mode)"
    )
    
    # Serper-specific
    serper_config = config.get("serper", {})
    parser.add_argument("--country", default=serper_config.get("country", "us"))
    parser.add_argument("--language", default=serper_config.get("language", "en"))
    parser.add_argument(
        "--type", 
        dest="search_type", 
        default=serper_config.get("type", "search"),
        choices=["search", "news", "images", "videos", "places", "shopping"]
    )
    parser.add_argument(
        "--time-range", 
        choices=["hour", "day", "week", "month", "year"]
    )
    
    # Tavily-specific
    tavily_config = config.get("tavily", {})
    parser.add_argument(
        "--depth", 
        default=tavily_config.get("depth", "basic"), 
        choices=["basic", "advanced"]
    )
    parser.add_argument(
        "--topic", 
        default=tavily_config.get("topic", "general"), 
        choices=["general", "news"]
    )
    parser.add_argument("--raw-content", action="store_true")
    
    # Querit-specific
    querit_config = config.get("querit", {})
    parser.add_argument(
        "--querit-base-url",
        default=querit_config.get("base_url", "https://api.querit.ai"),
        help="Querit API base URL"
    )
    parser.add_argument(
        "--querit-base-path",
        default=querit_config.get("base_path", "/v1/search"),
        help="Querit API path"
    )

    # Linkup-specific
    linkup_config = config.get("linkup", {})
    parser.add_argument(
        "--linkup-depth",
        default=linkup_config.get("depth", "standard"),
        choices=["fast", "standard", "deep"],
        help="Linkup search depth: fast, standard, or deep"
    )
    parser.add_argument(
        "--linkup-output-type",
        default=linkup_config.get("output_type", "searchResults"),
        choices=["searchResults", "sourcedAnswer"],
        help="Linkup output type"
    )

    # Exa-specific
    exa_config = config.get("exa", {})
    parser.add_argument(
        "--exa-type",
        default=exa_config.get("type", "neural"),
        choices=["neural", "fast", "auto", "keyword", "instant"],
        help="Exa search type (for standard search, ignored when --exa-depth is set)"
    )
    parser.add_argument(
        "--exa-depth",
        default=exa_config.get("depth", "normal"),
        choices=["normal", "deep", "deep-reasoning"],
        help="Exa search depth: deep (synthesized, 4-12s), deep-reasoning (cross-reference, 12-50s)"
    )
    parser.add_argument(
        "--exa-verbosity",
        default=exa_config.get("verbosity", "standard"),
        choices=["compact", "standard", "full"],
        help="Exa text verbosity for content extraction"
    )
    parser.add_argument(
        "--category",
        choices=[
            "company", "research paper", "news", "pdf", "github", 
            "tweet", "personal site", "linkedin profile"
        ]
    )
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--similar-url")

    # Firecrawl-specific
    firecrawl_config = config.get("firecrawl", {})
    parser.add_argument(
        "--firecrawl-scrape",
        action="store_true",
        help="Firecrawl: scrape result pages and include markdown as raw_content"
    )
    parser.add_argument(
        "--firecrawl-sources",
        nargs="+",
        default=firecrawl_config.get("sources", ["web"]),
        choices=["web", "news", "images"],
        help="Firecrawl result sources"
    )
    
    # You.com-specific
    you_config = config.get("you", {})
    parser.add_argument(
        "--you-safesearch",
        default=you_config.get("safesearch", "moderate"),
        choices=["off", "moderate", "strict"],
        help="You.com SafeSearch filter"
    )
    parser.add_argument(
        "--freshness",
        choices=["day", "week", "month", "year"],
        help="Filter results by recency (You.com/Serper)"
    )
    parser.add_argument(
        "--livecrawl",
        choices=["web", "news", "all"],
        help="You.com: fetch full page content"
    )
    parser.add_argument(
        "--no-news",
        action="store_true",
        help="You.com: exclude news results (included by default)"
    )
    
    # SearXNG-specific
    searxng_config = config.get("searxng", {})
    parser.add_argument(
        "--searxng-url",
        default=searxng_config.get("instance_url"),
        help="SearXNG instance URL (e.g., https://searx.example.com)"
    )
    parser.add_argument(
        "--searxng-safesearch",
        type=int,
        default=searxng_config.get("safesearch", 0),
        choices=[0, 1, 2],
        help="SearXNG SafeSearch: 0=off, 1=moderate, 2=strict"
    )
    parser.add_argument(
        "--engines",
        nargs="+",
        default=searxng_config.get("engines"),
        help="SearXNG: specific engines to use (e.g., google bing duckduckgo)"
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        help="SearXNG: search categories (general, images, news, videos, etc.)"
    )
    
    # Domain filters
    parser.add_argument("--include-domains", nargs="+")
    parser.add_argument("--exclude-domains", nargs="+")
    
    # Output
    parser.add_argument("--compact", action="store_true")
    parser.add_argument(
        "--quality-report",
        action="store_true",
        help="Attach transparent routing/result diagnostics to the JSON output"
    )
    parser.add_argument(
        "--mode",
        default="normal",
        choices=["normal", "research"],
        help="Search mode: normal single-provider route or research multi-provider + extraction"
    )
    parser.add_argument(
        "--research-providers",
        nargs="+",
        help="Explicit provider list for --mode research"
    )
    parser.add_argument(
        "--research-extract-count",
        type=int,
        default=3,
        help="Number of top research-mode URLs to extract for grounding"
    )
    parser.add_argument(
        "--research-time-budget",
        type=float,
        default=55.0,
        help="Best-effort wall-clock budget for research mode; skips remaining providers/extraction between calls when exhausted"
    )
    
    # Caching options
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=DEFAULT_CACHE_TTL,
        help=f"Cache TTL in seconds (default: {DEFAULT_CACHE_TTL} = 1 hour)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache (always fetch fresh results)"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached results and exit"
    )
    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cache statistics and exit"
    )
    
    args = parser.parse_args()
    
    # Handle cache management commands first (before query validation)
    if args.clear_cache:
        result = cache_clear()
        indent = None if args.compact else 2
        print(json.dumps(result, indent=indent, ensure_ascii=False))
        return
    
    if args.cache_stats:
        result = cache_stats()
        indent = None if args.compact else 2
        print(json.dumps(result, indent=indent, ensure_ascii=False))
        return

    if args.extract_urls is not None:
        result = extract_plus(
            urls=args.extract_urls,
            provider=args.provider or "auto",
            output_format=args.output_format,
            include_images=args.extract_images,
            include_raw_html=args.include_raw_html,
            render_js=args.render_js,
            config=config,
        )
        indent = None if args.compact else 2
        print(json.dumps(result, indent=indent, ensure_ascii=False))
        return
    
    if not args.query and not args.similar_url:
        parser.error("--query is required (unless using --similar-url with Exa)")
    
    # Handle --explain-routing
    if args.explain_routing:
        if not args.query:
            parser.error("--query is required for --explain-routing")
        explanation = explain_routing(args.query, config)
        indent = None if args.compact else 2
        print(json.dumps(explanation, indent=indent, ensure_ascii=False))
        return
    
    # Determine provider
    if args.provider == "auto" or (args.provider is None and not args.similar_url):
        if args.query:
            routing = auto_route_provider(args.query, config)
            provider = routing["provider"]
            routing_info = {
                "auto_routed": True,
                "provider": provider,
                "confidence": routing["confidence"],
                "confidence_level": routing["confidence_level"],
                "reason": routing["reason"],
                "routing_policy": routing.get("routing_policy", ROUTING_POLICY),
                "top_signals": routing["top_signals"],
                "scores": routing["scores"],
                "auto_allow_excluded": routing.get("auto_allow_excluded", []),
                "analysis_summary": routing.get("analysis_summary", {}),
            }
        else:
            provider = "exa"
            routing_info = {
                "auto_routed": True,
                "provider": "exa",
                "confidence": 1.0,
                "confidence_level": "high",
                "reason": "similar_url_specified",
                "routing_policy": ROUTING_POLICY,
            }
    else:
        provider = args.provider or "serper"
        routing_info = {"auto_routed": False, "provider": provider, "routing_policy": ROUTING_POLICY}
    
    # Build provider fallback list
    auto_config = config.get("auto_routing", {})
    provider_priority = auto_config.get("provider_priority", ["tavily", "linkup", "parallel", "exa", "firecrawl", "perplexity", "kilo-perplexity", "brave", "serper", "you", "searxng", "serpbase", "querit"])
    disabled_providers = auto_config.get("disabled_providers", [])

    # Start with the selected provider, then try others in priority order.
    # Explicit provider calls are strict by default: requested provider must be
    # the actual provider. Use --allow-fallback to opt into legacy fallback.
    # Fixed-provider mode is intentionally strict: if auto-routing is disabled
    # and the saved default was selected via provider=auto, do not silently
    # fall back to other providers. Users who want fallback should keep
    # auto-routing enabled and tune priority/fallback instead.
    explicit_provider_mode = args.provider not in (None, "auto")
    fixed_provider_mode = (
        auto_config.get("enabled", True) is False
        and provider == config.get("default_provider")
        and (args.provider == "auto" or (args.provider is None and not args.similar_url))
    )
    strict_provider_mode = fixed_provider_mode or (explicit_provider_mode and not args.allow_fallback)
    providers_to_try = [provider] if provider else []
    if not strict_provider_mode:
        for p in provider_priority:
            if p not in providers_to_try and p not in disabled_providers and _provider_auto_allowed(p, auto_config) and get_api_key(p, config):
                providers_to_try.append(p)

    # Skip providers currently in cooldown
    eligible_providers = []
    cooldown_skips = []
    for p in providers_to_try:
        in_cd, remaining = provider_in_cooldown(p)
        if in_cd:
            cooldown_skips.append({"provider": p, "cooldown_remaining_seconds": remaining})
        else:
            eligible_providers.append(p)

    if not eligible_providers:
        eligible_providers = providers_to_try[:1]

    # Helper function to execute search for a provider
    def execute_search(prov: str) -> Dict[str, Any]:
        key = validate_api_key(prov, config)
        if prov == "serper":
            return search_serper(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                country=args.country,
                language=args.language,
                search_type=args.search_type,
                time_range=args.time_range,
                include_images=args.images,
            )
        elif prov == "serpbase":
            serpbase_config = config.get("serpbase", {})
            return search_serpbase(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                country=serpbase_config.get("country", args.country),
                language=serpbase_config.get("language", args.language),
                page=int(serpbase_config.get("page", 1)),
                api_url=serpbase_config.get("api_url", "https://api.serpbase.dev/google/search"),
                timeout=int(serpbase_config.get("timeout", 30)),
            )
        elif prov == "brave":
            brave_config = config.get("brave", {})
            return search_brave(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                country=brave_config.get("country", args.country),
                language=brave_config.get("search_lang", args.language),
                time_range=args.time_range or args.freshness,
                safesearch=brave_config.get("safesearch", "moderate"),
            )
        elif prov == "tavily":
            return search_tavily(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                depth=args.depth,
                topic=args.topic,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                include_images=args.images,
                include_raw_content=args.raw_content,
            )
        elif prov == "linkup":
            linkup_config = config.get("linkup", {})
            return search_linkup(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                depth=args.linkup_depth,
                output_type=args.linkup_output_type,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                api_url=linkup_config.get("api_url", "https://api.linkup.so/v1/search"),
                timeout=int(linkup_config.get("timeout", 30)),
            )
        elif prov == "querit":
            return search_querit(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                language=args.language,
                country=args.country,
                time_range=args.time_range or args.freshness,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                base_url=args.querit_base_url,
                base_path=args.querit_base_path,
                timeout=int(querit_config.get("timeout", 30)),
            )
        elif prov == "exa":
            # CLI --exa-depth overrides; fallback to auto-routing suggestion
            exa_depth = args.exa_depth
            if exa_depth == "normal" and routing_info.get("exa_depth") in ("deep", "deep-reasoning"):
                exa_depth = routing_info["exa_depth"]
            return search_exa(
                query=args.query or "",
                api_key=key,
                max_results=args.max_results,
                search_type=args.exa_type,
                exa_depth=exa_depth,
                category=args.category,
                start_date=args.start_date,
                end_date=args.end_date,
                similar_url=args.similar_url,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                text_verbosity=args.exa_verbosity,
            )
        elif prov == "firecrawl":
            firecrawl_config = config.get("firecrawl", {})
            return search_firecrawl(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                country=firecrawl_config.get("country", args.country),
                time_range=args.time_range or args.freshness,
                sources=args.firecrawl_sources,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                scrape_markdown=args.firecrawl_scrape or args.raw_content,
                ignore_invalid_urls=firecrawl_config.get("ignore_invalid_urls", False),
                api_url=firecrawl_config.get("api_url", "https://api.firecrawl.dev/v2/search"),
                timeout_ms=int(firecrawl_config.get("timeout", 30000)),
            )
        elif prov == "parallel":
            parallel_config = config.get("parallel", {})
            return search_parallel(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                include_domains=args.include_domains,
                exclude_domains=args.exclude_domains,
                api_url=parallel_config.get("api_url", "https://api.parallel.ai/v1/search"),
                timeout=int(parallel_config.get("timeout", 45)),
                client_model=parallel_config.get("client_model"),
            )
        elif prov in {"perplexity", "kilo-perplexity"}:
            perplexity_config = config.get(prov, {})
            defaults = DEFAULT_CONFIG.get(prov, {})
            return search_perplexity(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                model=perplexity_config.get("model", defaults.get("model", "sonar-pro")),
                api_url=perplexity_config.get("api_url", defaults.get("api_url", "https://api.perplexity.ai/chat/completions")),
                freshness=getattr(args, "freshness", None),
                provider_name=prov,
            )
        elif prov == "you":
            return search_you(
                query=args.query,
                api_key=key,
                max_results=args.max_results,
                country=args.country,
                language=args.language,
                freshness=args.freshness,
                safesearch=args.you_safesearch,
                include_news=not args.no_news,
                livecrawl=args.livecrawl,
            )
        elif prov == "searxng":
            # For SearXNG, 'key' is actually the instance URL
            instance_url = args.searxng_url or key
            if instance_url:
                instance_url = _validate_searxng_url(instance_url)
            return search_searxng(
                query=args.query,
                instance_url=instance_url,
                max_results=args.max_results,
                categories=args.categories,
                engines=args.engines,
                language=args.language,
                time_range=args.time_range,
                safesearch=args.searxng_safesearch,
            )
        else:
            raise ValueError(f"Unknown provider: {prov}")

    def execute_with_retry(prov: str) -> Dict[str, Any]:
        return execute_provider_with_retry(prov, lambda: execute_search(prov))

    cache_context = {
        "locale": f"{args.country}:{args.language}",
        "freshness": args.freshness,
        "time_range": args.time_range,
        "include_domains": sorted(args.include_domains) if args.include_domains else None,
        "exclude_domains": sorted(args.exclude_domains) if args.exclude_domains else None,
        "topic": args.topic,
        "search_engines": sorted(args.engines) if args.engines else None,
        "include_news": not args.no_news,
        "search_type": args.search_type,
        "exa_type": args.exa_type,
        "exa_depth": args.exa_depth,
        "exa_verbosity": args.exa_verbosity,
        "category": args.category,
        "similar_url": args.similar_url,
        "mode": args.mode,
        "quality_report": args.quality_report,
    }

    providers_considered = providers_to_try.copy()

    if args.mode == "research":
        available_research_providers = {
            p for p in providers_to_try
            if p not in disabled_providers and _provider_auto_allowed(p, auto_config) and get_api_key(p, config) and not provider_in_cooldown(p)[0]
        }
        if provider and get_api_key(provider, config) and not provider_in_cooldown(provider)[0]:
            available_research_providers.add(provider)
        if args.research_providers:
            research_providers = [
                p for p in args.research_providers
                if p not in disabled_providers and _provider_auto_allowed(p, auto_config) and get_api_key(p, config) and not provider_in_cooldown(p)[0]
            ]
        else:
            research_providers = select_research_providers(
                primary_provider=provider,
                provider_priority=provider_priority,
                available_providers=available_research_providers,
                max_providers=3,
            )

        if not research_providers:
            error_result = {
                "error": "No configured providers available for research mode",
                "provider": provider,
                "query": args.query,
                "routing": routing_info,
                "cooldown_skips": cooldown_skips,
            }
            print(json.dumps(error_result, indent=2), file=sys.stderr)
            sys.exit(1)

        result = run_research_mode(
            query=args.query,
            research_providers=research_providers,
            execute_search=execute_with_retry,
            extract_urls=lambda urls: extract_plus(
                urls=urls,
                provider="auto",
                output_format="markdown",
                config=config,
            ),
            max_results=args.max_results,
            max_extract_urls=args.research_extract_count,
            time_budget_seconds=args.research_time_budget,
        )
        routing_info["mode"] = "research"
        routing_info["provider"] = "research"
        result["routing"].update(routing_info)
        result["quality_report"] = build_quality_report(
            query=args.query,
            result=result,
            routing_info=routing_info,
            providers_considered=providers_considered,
            eligible_providers=research_providers,
            cooldown_skips=cooldown_skips,
            errors=result.get("routing", {}).get("provider_errors", []),
        )
        indent = None if args.compact else 2
        print(json.dumps(result, indent=indent, ensure_ascii=False))
        return

    # Check cache first (unless --no-cache is set)
    cached_result = None
    cache_hit = False
    if not args.no_cache and args.query:
        cached_result = cache_get(
            query=args.query,
            provider=provider,
            max_results=args.max_results,
            ttl=args.cache_ttl,
            params=cache_context,
        )
        if cached_result:
            cache_hit = True
            result = {k: v for k, v in cached_result.items() if not k.startswith("_cache_")}
            result["cached"] = True
            result["cache_age_seconds"] = int(time.time() - cached_result.get("_cache_timestamp", 0))

    errors = []
    successful_provider = None
    successful_results: List[Tuple[str, Dict[str, Any]]] = []
    result = None if not cache_hit else result

    for idx, current_provider in enumerate(eligible_providers):
        if cache_hit:
            successful_provider = provider
            break
        try:
            provider_result = execute_with_retry(current_provider)
            reset_provider_health(current_provider)
            successful_results.append((current_provider, provider_result))
            successful_provider = current_provider

            # If we have enough results, stop.
            if len(provider_result.get("results", [])) >= args.max_results:
                break

            # Only continue collecting from lower-priority providers when fallback was needed.
            if not errors:
                break
        except Exception as e:
            error_msg = str(e)
            cooldown_info = mark_provider_failure(current_provider, error_msg)
            errors.append({
                "provider": current_provider,
                "error": error_msg,
                "cooldown_seconds": cooldown_info.get("cooldown_seconds"),
            })
            if len(eligible_providers) > 1:
                remaining = eligible_providers[idx + 1:]
                if remaining:
                    print(json.dumps({
                        "fallback": True,
                        "failed_provider": current_provider,
                        "error": error_msg,
                        "trying_next": remaining[0],
                    }), file=sys.stderr)
            continue

    if successful_results:
        if len(successful_results) == 1:
            result = successful_results[0][1]
        else:
            primary = successful_results[0][1].copy()
            deduped_results, dedup_count = deduplicate_results_across_providers(successful_results, args.max_results)
            primary["results"] = deduped_results
            primary["deduplicated"] = dedup_count > 0
            primary.setdefault("metadata", {})
            primary["metadata"]["dedup_count"] = dedup_count
            primary["metadata"]["providers_merged"] = [p for p, _ in successful_results]
            result = primary

    if result is not None:
        if successful_provider != provider:
            routing_info["fallback_used"] = True
            routing_info["original_provider"] = provider
            routing_info["provider"] = successful_provider
            routing_info["fallback_errors"] = errors

        if cooldown_skips:
            routing_info["cooldown_skips"] = cooldown_skips

        routing_class = routing_info.get("analysis_summary", {}).get("routing_class", "general")
        if not cache_hit and isinstance(result.get("results"), list):
            reranked, rerank_metadata = rerank_results_for_intent(args.query or "", routing_class, result.get("results", []))
            result["results"] = reranked
            if rerank_metadata.get("reranked"):
                result.setdefault("metadata", {})["intent_rerank"] = rerank_metadata

        result["routing"] = routing_info

        if not cache_hit and not args.no_cache and args.query:
            cache_put(
                query=args.query,
                provider=successful_provider or provider,
                max_results=args.max_results,
                result=result,
                params=cache_context,
            )

        result["cached"] = bool(cache_hit)
        if "deduplicated" not in result:
            result["deduplicated"] = False
            result.setdefault("metadata", {})
            result["metadata"].setdefault("dedup_count", 0)

        if args.quality_report:
            result["quality_report"] = build_quality_report(
                query=args.query,
                result=result,
                routing_info=routing_info,
                providers_considered=providers_considered,
                eligible_providers=eligible_providers,
                cooldown_skips=cooldown_skips,
                errors=errors,
            )

        indent = None if args.compact else 2
        print(json.dumps(result, indent=indent, ensure_ascii=False))
    else:
        error_result = {
            "error": "All providers failed",
            "provider": provider,
            "query": args.query,
            "routing": routing_info,
            "provider_errors": errors,
            "cooldown_skips": cooldown_skips,
        }
        print(json.dumps(error_result, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
