"""Perplexity-compatible provider adapter."""

from __future__ import annotations

import re
from typing import Optional

try:  # pragma: no cover - import style depends on CLI/package execution
    from ..http_client import make_request
except ImportError:  # pragma: no cover
    from http_client import make_request  # type: ignore


def _title_from_url(url: str) -> str:
    """Fallback title helper; search.py patches this for compatibility."""
    if not url:
        return "Untitled"
    return url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").title() or url


def search_perplexity(
    query: str,
    api_key: str,
    max_results: int = 5,
    model: str = "sonar-pro",
    api_url: str = "https://api.perplexity.ai/chat/completions",
    freshness: Optional[str] = None,
    provider_name: str = "perplexity",
) -> dict:
    """Search/answer using the native Perplexity API or a compatible gateway.

    Args:
        query: Search query
        api_key: Provider API key
        max_results: Maximum results to return
        model: Perplexity-compatible model to use
        api_url: Chat completions endpoint
        freshness: Filter by recency — 'day', 'week', 'month', 'year' (maps to
                   Perplexity's search_recency_filter parameter)
        provider_name: Result provider label (perplexity or kilo-perplexity)
    """
    # Map generic freshness values to Perplexity's search_recency_filter
    recency_map = {"day": "day", "pd": "day", "week": "week", "pw": "week", "month": "month", "pm": "month", "year": "year", "py": "year"}
    recency_filter = recency_map.get(freshness or "", None)

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Answer with concise factual summary and include source URLs."},
            {"role": "user", "content": query},
        ],
        "temperature": 0.2,
    }
    if recency_filter:
        body["search_recency_filter"] = recency_filter

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = make_request(api_url, headers, body)
    choices = data.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    answer = (message.get("content") or "").strip()

    # Prefer the structured citations array from Perplexity API response
    api_citations = data.get("citations", [])

    # Fallback: extract URLs from answer text if API doesn't provide citations
    if not api_citations:
        api_citations = []
        seen = set()
        for u in re.findall(r"https?://[^\s)\]}>\"']+", answer):
            if u not in seen:
                seen.add(u)
                api_citations.append(u)

    results = []

    # Primary result: the synthesized answer itself
    if answer:
        # Clean citation markers [1][2] for the snippet
        clean_answer = re.sub(r'\[\d+\]', '', answer).strip()
        results.append({
            "title": f"Perplexity Answer: {query[:80]}",
            "url": "https://www.perplexity.ai",
            "snippet": clean_answer[:500],
            "score": 1.0,
        })

    # Source results from citations
    for i, citation in enumerate(api_citations[:max_results - 1]):
        # citations can be plain URL strings or dicts with url/title
        if isinstance(citation, str):
            url = citation
            title = _title_from_url(url)
        else:
            url = citation.get("url", "")
            title = citation.get("title") or _title_from_url(url)
        results.append({
            "title": title,
            "url": url,
            "snippet": f"Source cited in Perplexity answer [citation {i+1}]",
            "score": round(0.9 - i * 0.1, 3),
        })

    return {
        "provider": provider_name,
        "query": query,
        "results": results,
        "images": [],
        "answer": answer,
        "metadata": {
            "model": model,
            "usage": data.get("usage", {}),
        }
    }
