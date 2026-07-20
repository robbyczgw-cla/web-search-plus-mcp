"""Deterministic, side-effect-free v3.1 Shadow policy evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from routing import QueryAnalyzer

if TYPE_CHECKING:
    from orchestrator_v3 import ProviderPlan


POLICY_ID = "shadow-quality"
POLICY_REVISION = "3.1"


def evaluate_shadow_policy(
    request: Any,
    plan: "ProviderPlan",
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate pure query-quality scores against Classic's candidate pool.

    This deliberately reuses only ``QueryAnalyzer.analyze``: it does not run
    adaptive performance adjustments, query-distribution tie breaking, provider
    calls, or any other execution-affecting behavior.
    """
    query = request.input["query"]
    analysis = QueryAnalyzer(dict(config)).analyze(query)
    scores = analysis["provider_scores"]
    candidates = tuple(dict.fromkeys(plan.candidate_order))
    ranked = [
        (provider, float(scores[provider]))
        for provider in candidates
        if provider in scores
    ]
    shadow_provider = (
        min(ranked, key=lambda item: (-item[1], item[0]))[0]
        if ranked
        else None
    )
    return {
        "observed": True,
        "policy_id": POLICY_ID,
        "policy_revision": POLICY_REVISION,
        "selected_provider": plan.selected_provider,
        "shadow_provider": shadow_provider,
        "agreement": plan.selected_provider == shadow_provider,
        "affected_execution": False,
    }
