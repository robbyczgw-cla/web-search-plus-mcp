"""Research mode orchestration helpers."""

from __future__ import annotations

import threading
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Dict, List, Optional, Tuple

try:
    from .daemon_tasks import DaemonTask
except ImportError:  # pragma: no cover - direct script execution
    from daemon_tasks import DaemonTask
try:
    from .diversity_v3 import DEFAULT_NEAR_DUPLICATE_THRESHOLD, rerank_duplicate_candidates
except ImportError:  # pragma: no cover - direct script execution
    from diversity_v3 import DEFAULT_NEAR_DUPLICATE_THRESHOLD, rerank_duplicate_candidates
try:
    from .quality import deduplicate_results_across_providers
except ImportError:  # pragma: no cover - direct script execution
    from quality import deduplicate_results_across_providers


# Small real-time grace given to already-submitted provider calls once the
# (possibly fake-clock) budget reads as exhausted, so completed futures can
# still be harvested without blocking on slow ones.
_RESULT_GRACE_SECONDS = 0.25


def run_research_mode(
    query: str,
    research_providers: List[str],
    execute_search,
    extract_urls,
    max_results: int,
    max_extract_urls: int = 3,
    time_budget_seconds: float | None = None,
    now_fn=None,
    max_workers: int | None = None,
    on_provider_timeout=None,
    diversity_rerank: bool = False,
    near_duplicate_threshold: float = DEFAULT_NEAR_DUPLICATE_THRESHOLD,
) -> Dict[str, Any]:
    """Run broad search, deduplicate, then extract top sources for grounding.

    Research mode is intentionally best-effort: provider/extraction failures should
    produce diagnostics and partial search results instead of throwing away the
    whole response. Provider searches run concurrently to keep the wall-clock cost
    close to the slowest single provider rather than the sum of all of them. The
    optional time budget gates which providers are launched (checked before each
    submission, so a tight budget still skips later providers deterministically),
    bounds how long already-launched providers may run, and gates whether
    extraction runs at all — so the budget caps total wall-clock time instead of
    only limiting how many providers start.

    Result ordering is preserved by provider submission order regardless of which
    provider finishes first, so deduplication stays deterministic.
    """
    provider_errors: List[Dict[str, Any]] = []
    now = now_fn or time.monotonic
    start = now()

    def remaining_budget() -> Optional[float]:
        if time_budget_seconds is None:
            return None
        return time_budget_seconds - (now() - start)

    # Submit providers (budget gate is sequential/deterministic); the actual
    # provider HTTP calls run concurrently on daemon threads. Daemon threads —
    # unlike ThreadPoolExecutor workers — are not joined at interpreter exit,
    # so an overdue provider cannot stall CLI/subprocess shutdown either.
    pending: List[Tuple[int, str]] = []
    tasks: Dict[int, DaemonTask] = {}
    workers = max_workers or max(1, len(research_providers))
    gate = threading.Semaphore(workers)

    def run_gated(provider_name: str) -> Dict[str, Any]:
        with gate:
            return execute_search(provider_name)

    for index, provider in enumerate(research_providers):
        remaining = remaining_budget()
        if remaining is not None and remaining <= 0:
            provider_errors.append({"provider": provider, "error": "skipped: research time budget exhausted"})
            continue
        tasks[index] = DaemonTask(run_gated, provider)
        pending.append((index, provider))

    results_by_index: Dict[int, Tuple[str, Dict[str, Any]]] = {}
    for index, provider in pending:
        remaining = remaining_budget()
        if remaining is not None and remaining <= 0:
            # Budget gone: give already-submitted calls a short real-time grace
            # so finished tasks are still harvested without blocking on slow ones.
            timeout = _RESULT_GRACE_SECONDS
        else:
            timeout = remaining
        try:
            results_by_index[index] = (provider, tasks[index].result(timeout=timeout))
        except FuturesTimeoutError:
            if on_provider_timeout is not None:
                on_provider_timeout(provider)
            provider_errors.append({"provider": provider, "error": "timed out: research time budget exhausted"})
        except Exception as e:
            provider_errors.append({"provider": provider, "error": str(e)})

    provider_results: List[Tuple[str, Dict[str, Any]]] = [
        results_by_index[index] for index in sorted(results_by_index)
    ]

    diversity_duplicates = []
    if diversity_rerank:
        # The normal merge drops cross-provider URL duplicates.  The explicit
        # diversity mode instead retains every candidate long enough to move
        # duplicate URLs and snippets behind the diverse head, then applies
        # the caller's ordinary result-count cap.
        merged_candidates: List[Dict[str, Any]] = []
        for provider_name, payload in provider_results:
            for item in payload.get("results", []):
                if not isinstance(item, dict):
                    continue
                candidate = item.copy()
                candidate.setdefault("provider", provider_name)
                merged_candidates.append(candidate)
        reranked_candidates, diversity_duplicates = rerank_duplicate_candidates(
            merged_candidates, near_duplicate_threshold=near_duplicate_threshold
        )
        deduped = reranked_candidates[:max_results]
        dedup_count = 0
    else:
        deduped, dedup_count = deduplicate_results_across_providers(provider_results, max_results)
    urls = [r.get("url") for r in deduped if r.get("url")][:max(0, max_extract_urls)]
    extracted = {"provider": None, "results": []}
    extraction_error = None
    if urls:
        remaining = remaining_budget()
        if remaining is not None and remaining <= 0:
            extraction_error = "skipped: research time budget exhausted"
        elif remaining is None:
            try:
                extracted = extract_urls(urls) or {"provider": None, "results": []}
            except Exception as e:
                extraction_error = str(e)
                extracted = {"provider": None, "results": []}
        else:
            # Run extraction on a daemon thread so the remaining budget bounds it too.
            try:
                extracted = DaemonTask(extract_urls, urls).result(timeout=remaining) or {"provider": None, "results": []}
            except FuturesTimeoutError:
                extraction_error = "timed out: research time budget exhausted"
                extracted = {"provider": None, "results": []}
            except Exception as e:
                extraction_error = str(e)
                extracted = {"provider": None, "results": []}

    routing = {
        "providers_queried": [p for p, _ in provider_results],
        "provider_errors": provider_errors,
        "extraction_provider": extracted.get("provider"),
    }
    if extraction_error:
        routing["extraction_error"] = extraction_error

    source_summaries = extracted.get("results", []) or []

    metadata = {
        "dedup_count": dedup_count,
        "providers_merged": [p for p, _ in provider_results],
        "extracted_url_count": len(source_summaries),
    }
    if diversity_rerank:
        metadata["diversity_reranked"] = len(diversity_duplicates)

    return {
        "mode": "research",
        "provider": "research",
        "query": query,
        "results": deduped,
        "source_summaries": source_summaries,
        "routing": routing,
        "metadata": metadata,
    }
