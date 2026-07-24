from copy import deepcopy
import time

import pytest

from web_search_plus_mcp.config import DEFAULT_CONFIG, _validate_runtime_config
from web_search_plus_mcp.research import run_research_mode


def _payload(provider: str, urls: list[str]) -> dict:
    return {
        "provider": provider,
        "results": [
            {"url": url, "title": f"{provider}-{index}", "description": "result"}
            for index, url in enumerate(urls)
        ],
    }


def test_completion_order_quorum_preempts_only_unfinished_provider():
    def execute(provider: str) -> dict:
        if provider == "slow":
            time.sleep(2.0)
            return _payload(provider, ["https://slow.example/a"])
        if provider == "fast-a":
            return _payload(provider, ["https://one.example/a"])
        return _payload(
            provider,
            ["https://two.example/a", "https://three.example/a"],
        )

    started = time.monotonic()
    result = run_research_mode(
        query="completion quorum",
        research_providers=["slow", "fast-a", "fast-b"],
        execute_search=execute,
        extract_urls=lambda _urls: {"provider": None, "results": []},
        max_results=3,
        max_extract_urls=0,
        time_budget_seconds=5.0,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert result["routing"]["providers_queried"] == ["fast-a", "fast-b"]
    assert result["routing"]["provider_errors"] == [
        {"provider": "slow", "error": "preempted_after_quorum"}
    ]
    assert result["metadata"]["research_quorum"] == {
        "enabled": True,
        "triggered": True,
        "min_contributing_providers": 2,
        "result_target": 3,
        "min_unique_domains": 3,
        "contributing_providers": ["fast-a", "fast-b"],
        "deduplicated_result_count": 3,
        "unique_domain_count": 3,
    }


def test_low_domain_diversity_does_not_preempt_or_lose_recall():
    def execute(provider: str) -> dict:
        if provider == "slow":
            time.sleep(0.08)
        return _payload(provider, [f"https://same.example/{provider}"])

    result = run_research_mode(
        query="diversity guard",
        research_providers=["fast-a", "fast-b", "slow"],
        execute_search=execute,
        extract_urls=lambda _urls: {"provider": None, "results": []},
        max_results=3,
        max_extract_urls=0,
        quorum_min_unique_domains=3,
    )

    assert result["routing"]["providers_queried"] == ["fast-a", "fast-b", "slow"]
    assert result["routing"]["provider_errors"] == []
    assert result["metadata"]["research_quorum"]["triggered"] is False
    assert len(result["results"]) == 3


def test_duplicate_urls_do_not_manufacture_quorum():
    def execute(provider: str) -> dict:
        if provider == "slow":
            time.sleep(0.06)
        return _payload(provider, ["https://same.example/a"])

    result = run_research_mode(
        query="duplicate guard",
        research_providers=["first", "second", "slow"],
        execute_search=execute,
        extract_urls=lambda _urls: {"provider": None, "results": []},
        max_results=3,
        max_extract_urls=0,
        quorum_min_unique_domains=1,
    )

    assert result["routing"]["providers_queried"] == ["first", "second", "slow"]
    assert result["routing"]["provider_errors"] == []
    assert result["metadata"]["research_quorum"]["deduplicated_result_count"] == 1


def test_disabled_quorum_waits_for_slow_provider():
    def execute(provider: str) -> dict:
        if provider == "slow":
            time.sleep(0.06)
        return _payload(provider, [f"https://{provider}.example/a"])

    result = run_research_mode(
        query="disabled quorum",
        research_providers=["fast-a", "fast-b", "slow"],
        execute_search=execute,
        extract_urls=lambda _urls: {"provider": None, "results": []},
        max_results=3,
        max_extract_urls=0,
        quorum_enabled=False,
    )

    assert result["routing"]["providers_queried"] == ["fast-a", "fast-b", "slow"]
    assert result["routing"]["provider_errors"] == []
    assert result["metadata"]["research_quorum"]["enabled"] is False
    assert result["metadata"]["research_quorum"]["triggered"] is False


def test_invalid_quorum_config_is_rejected_and_valid_disable_is_preserved():
    invalid = deepcopy(DEFAULT_CONFIG)
    invalid["quality"]["research_quorum"]["enabled"] = "yes"
    with pytest.raises(ValueError, match="quality.research_quorum.enabled"):
        _validate_runtime_config(invalid)

    valid = deepcopy(DEFAULT_CONFIG)
    valid["quality"]["research_quorum"].update(
        {
            "enabled": False,
            "min_contributing_providers": 3,
            "result_target_cap": 4,
            "min_unique_domains": 2,
        }
    )
    validated = _validate_runtime_config(valid)
    assert validated["quality"]["research_quorum"] == {
        "enabled": False,
        "min_contributing_providers": 3,
        "result_target_cap": 4,
        "min_unique_domains": 2,
    }
