from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from web_search_plus_mcp import shadow_policy_v3 as shadow
from web_search_plus_mcp.orchestrator_v3 import ProviderPlan


def _request(query: str = "quality test") -> SimpleNamespace:
    return SimpleNamespace(input={"query": query})


def test_evaluator_is_deterministic_and_breaks_ties_lexicographically(
    monkeypatch,
) -> None:
    calls: list[str] = []

    class Analyzer:
        def __init__(self, _config: dict) -> None:
            pass

        def analyze(self, query: str) -> dict:
            calls.append(query)
            return {"provider_scores": {"serper": 4.0, "linkup": 4.0}}

    monkeypatch.setattr(shadow, "QueryAnalyzer", Analyzer)
    plan = ProviderPlan(("serper", "linkup"), "serper")

    first = shadow.evaluate_shadow_policy(_request(), plan, {})
    second = shadow.evaluate_shadow_policy(_request(), plan, {})

    assert first == second == {
        "observed": True,
        "policy_id": "shadow-quality",
        "policy_revision": "3.1",
        "selected_provider": "serper",
        "shadow_provider": "linkup",
        "agreement": False,
        "affected_execution": False,
    }
    assert calls == ["quality test", "quality test"]


def test_evaluator_restricts_ranking_to_the_classic_candidate_pool(monkeypatch) -> None:
    class Analyzer:
        def __init__(self, _config: dict) -> None:
            pass

        def analyze(self, _query: str) -> dict:
            return {
                "provider_scores": {
                    "exa": 100.0,
                    "linkup": 7.0,
                    "serper": 1.0,
                }
            }

    monkeypatch.setattr(shadow, "QueryAnalyzer", Analyzer)
    plan = ProviderPlan(("serper", "linkup"), "serper")

    observation = shadow.evaluate_shadow_policy(_request(), plan, {})

    assert observation["shadow_provider"] == "linkup"
    assert observation["shadow_provider"] in plan.candidate_order


def test_evaluator_is_side_effect_free_for_plan_and_config(monkeypatch) -> None:
    class Analyzer:
        def __init__(self, _config: dict) -> None:
            pass

        def analyze(self, _query: str) -> dict:
            return {"provider_scores": {"serper": 1.0}}

    monkeypatch.setattr(shadow, "QueryAnalyzer", Analyzer)
    config = {"auto_routing": {"provider_priority": ["linkup", "serper"]}}
    plan = ProviderPlan(
        ("serper",),
        "serper",
        routing_metadata={"analysis_summary": {"routing_class": "policy_pdf"}},
    )
    original_config = deepcopy(config)
    original_metadata = deepcopy(plan.routing_metadata)

    observation = shadow.evaluate_shadow_policy(_request(), plan, config)

    assert observation["agreement"] is True
    assert config == original_config
    assert plan.routing_metadata == original_metadata


def test_legacy_request_projection_propagates_config_policy_mode() -> None:
    from compat_v3 import legacy_request_to_v3
    from contract_v3 import Capability

    default = legacy_request_to_v3(Capability.SEARCH, {"query": "q"})
    assert default.routing["policy_mode"] == "classic"

    shadow = legacy_request_to_v3(
        Capability.SEARCH, {"query": "q"}, policy_mode="shadow"
    )
    assert shadow.routing["policy_mode"] == "shadow"

    # Unknown values fail closed to Classic rather than propagating.
    other = legacy_request_to_v3(
        Capability.SEARCH, {"query": "q"}, policy_mode="canary"
    )
    assert other.routing["policy_mode"] == "classic"
