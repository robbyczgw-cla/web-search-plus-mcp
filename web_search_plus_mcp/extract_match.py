"""Pair provider extract items with the URLs that were requested.

Extraction owes the caller exactly one outcome per requested URL, in request
order. Search dedup compares canonical URLs; extraction must not, because
``/page?ref=1`` and ``/page?ref=2`` are two requests even when they share a
canonical form. This module only decides which provider item answers which
request, and refuses to guess when the item carries no evidence.

No network access and no imports beyond ``urls``, so host adapters can use it.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
import re
from urllib.parse import quote, urlsplit, urlunsplit

from .urls import canonical_url

# Keys under which providers report the URL they were *asked* for when the
# item's own ``url`` is a redirect target (Firecrawl ``metadata.sourceURL``).
SOURCE_URL_KEYS = ("sourceURL", "sourceUrl", "source_url", "requested_url", "requestedUrl")


def item_source_urls(item: Mapping[str, Any]) -> List[str]:
    """URLs an item reports as its request/source URL (item level, then metadata)."""
    found: List[str] = []
    holders = [item]
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        holders.append(metadata)
    for holder in holders:
        for key in SOURCE_URL_KEYS:
            value = holder.get(key)
            if isinstance(value, str) and value and value not in found:
                found.append(value)
    return found


def _rewrite_key(url: str) -> str:
    """Ignore HTTP upgrades and percent spelling, not encoded path separators."""
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return ""
        path = quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
        path = re.sub(r"%[0-9a-fA-F]{2}", lambda match: match[0].upper(), path)
        return canonical_url(urlunsplit(("https", parts.netloc, path, parts.query, parts.fragment)))
    except ValueError:
        return ""


def match_extract_items(
    urls: Sequence[str], items: Sequence[Any]
) -> Tuple[List[Optional[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Return ``(matched, unmatched)``.

    ``matched`` has one entry per requested URL (``None`` = still open).
    ``unmatched`` lists provider items that answered no requested URL.

    Order of evidence: exact URL, canonical URL, then the source URL the
    provider reports, then HTTP/percent spelling equivalence. A final lone
    item may answer a lone open URL (cross-host redirect), never an ambiguous
    batch by position. When several *different* requested spellings share one
    canonical form (``?ref=1`` / ``?ref=2``), a canonical or source-URL hit is
    ambiguous and only an exact hit may decide.
    """
    candidates = [item for item in items if isinstance(item, dict)]
    matched: List[Optional[Dict[str, Any]]] = [None] * len(urls)
    used = set()

    def item_keys(item: Dict[str, Any], source: bool) -> List[str]:
        return item_source_urls(item) if source else [str(item.get("url") or "")]

    def run_pass(key: Callable[[str], str], source: bool, *, ambiguity_check: bool) -> None:
        groups: Dict[str, List[int]] = {}
        for position, url in enumerate(urls):
            wanted = key(url)
            if wanted:
                groups.setdefault(wanted, []).append(position)
        for wanted, positions in groups.items():
            if ambiguity_check and len({urls[p] for p in positions}) > 1:
                continue
            for position in positions:
                if matched[position] is not None:
                    continue
                for index, item in enumerate(candidates):
                    if index in used:
                        continue
                    if any(key(value) == wanted for value in item_keys(item, source)):
                        matched[position] = item
                        used.add(index)
                        break

    run_pass(str, False, ambiguity_check=False)
    run_pass(canonical_url, False, ambiguity_check=True)
    run_pass(str, True, ambiguity_check=False)
    run_pass(canonical_url, True, ambiguity_check=True)
    run_pass(_rewrite_key, False, ambiguity_check=True)
    run_pass(_rewrite_key, True, ambiguity_check=True)

    open_positions = [position for position, item in enumerate(matched) if item is None]
    remaining = [index for index in range(len(candidates)) if index not in used]
    if len(open_positions) == len(remaining) == 1:
        position, index = open_positions[0], remaining[0]
        key = _rewrite_key(urls[position])
        # A singleton left after an exact ?ref hit is still ambiguous: the
        # remaining item could be another answer to that already-filled URL.
        if key and len({url for url in urls if _rewrite_key(url) == key}) == 1:
            matched[position] = candidates[index]
            used.add(index)

    # The very same URL requested twice has one answer. A provider that
    # answers it once (or dedups server-side) serves both requests.
    for position, url in enumerate(urls):
        if matched[position] is None:
            for earlier in range(position):
                if matched[earlier] is not None and urls[earlier] == url:
                    matched[position] = dict(matched[earlier])
                    break

    unmatched = [item for index, item in enumerate(candidates) if index not in used]
    return matched, unmatched
