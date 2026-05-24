"""Parallel search and extraction provider adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:  # pragma: no cover - import style depends on CLI/package execution
    from ..http_client import make_request
except ImportError:  # pragma: no cover
    from http_client import make_request  # type: ignore


def _title_from_url(url: str) -> str:
    """Fallback title helper; search.py patches this for compatibility."""
    if not url:
        return "Untitled"
    return url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").title() or url


def _normalize_extract_result(
    provider: str,
    url: str,
    title: str = "",
    content: str = "",
    raw_content: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Fallback normalize helper; search.py patches this for compatibility."""
    result = {
        "url": url,
        "title": title or _title_from_url(url),
        "content": content or "",
        "raw_content": raw_content if raw_content is not None else (content or ""),
        "provider": provider,
    }
    for key, value in extra.items():
        if value is not None:
            result[key] = value
    return result


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
    """Search using Parallel's web search API.

    Parallel returns source URLs plus long LLM-ready excerpts. Its API does not
    currently accept a generic max_results parameter, so results are trimmed
    locally to the requested count.
    """
    search_query = query
    if include_domains:
        search_query += " " + " ".join(f"site:{domain}" for domain in include_domains)
    if exclude_domains:
        search_query += " " + " ".join(f"-site:{domain}" for domain in exclude_domains)

    body: Dict[str, Any] = {
        "objective": query,
        "search_queries": [search_query],
    }
    if client_model:
        body["client_model"] = client_model

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    data = make_request(api_url, headers, body, timeout=timeout)

    raw_results = data.get("results") or []
    results = []
    for i, item in enumerate(raw_results[:max_results]):
        excerpts = item.get("excerpts") or []
        snippet_parts = []
        for excerpt in excerpts:
            if isinstance(excerpt, dict):
                snippet_parts.append(excerpt.get("text") or excerpt.get("content") or "")
            elif isinstance(excerpt, str):
                snippet_parts.append(excerpt)
        snippet = "\n\n".join(part for part in snippet_parts if part).strip()
        results.append({
            "title": item.get("title") or _title_from_url(item.get("url", "")),
            "url": item.get("url", ""),
            "snippet": snippet,
            "score": round(1.0 - i * 0.05, 3),
            "publish_date": item.get("publish_date"),
            "excerpts": excerpts,
        })

    answer = " ".join(r.get("snippet", "") for r in results[:3])[:1200]
    return {
        "provider": "parallel",
        "query": query,
        "results": results,
        "images": [],
        "answer": answer,
        "metadata": {
            "search_id": data.get("search_id"),
            "session_id": data.get("session_id"),
            "result_count_raw": len(raw_results),
        },
    }


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
    """Extract URL content using Parallel Extract.

    Parallel returns excerpts by default; request full_content explicitly and
    normalize it into the common markdown/content shape. HTML/raw-image options
    are accepted for tool compatibility but ignored when unsupported upstream.
    """
    _ = output_format, include_images, include_raw_html, render_js
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body: Dict[str, Any] = {
        "urls": urls,
        "max_chars_total": max_chars_total,
        "advanced_settings": {
            "full_content": {"max_chars_per_result": max_chars_per_result}
        },
    }
    if client_model:
        body["client_model"] = client_model

    data = make_request(api_url, headers, body, timeout=timeout)
    results: List[Dict[str, Any]] = []
    for item in data.get("results", []) or []:
        url = item.get("url") or ""
        excerpts = item.get("excerpts") or []
        excerpt_text = "\n\n".join(
            (ex.get("text") or ex.get("content") or "") if isinstance(ex, dict) else str(ex)
            for ex in excerpts
        ).strip()
        content = item.get("full_content") or item.get("markdown") or item.get("content") or excerpt_text
        results.append(_normalize_extract_result(
            "parallel",
            url,
            title=item.get("title", ""),
            content=content,
            raw_content=content,
            excerpts=excerpts or None,
            metadata={k: v for k, v in item.items() if k not in {"url", "title", "full_content", "markdown", "content", "excerpts"}},
        ))
    for failed in data.get("errors", []) or []:
        failed_url = failed.get("url", "") if isinstance(failed, dict) else ""
        results.append(_normalize_extract_result("parallel", failed_url, error=str(failed)))
    return {
        "provider": "parallel",
        "results": results,
        "metadata": {
            "search_id": data.get("search_id"),
            "session_id": data.get("session_id"),
        },
    }
