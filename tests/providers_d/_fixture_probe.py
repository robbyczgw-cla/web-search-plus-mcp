"""Subprocess probe for zero-core-edit SDK provider discovery in the MCP package."""
from __future__ import annotations

from web_search_plus_mcp import provider_registry, routing, search


def main() -> None:
    config = {
        "example_fixture": {"allow_public": True},
        "auto_routing": {"provider_priority": ["example-fixture"]},
    }

    spec = provider_registry.PROVIDER_SPECS["example-fixture"]
    assert spec.production is False
    assert spec.execute_search is not None
    assert "example-fixture" in provider_registry.SEARCH_PROVIDER_IDS
    assert "example-fixture" not in provider_registry.DEFAULT_PROVIDER_PRIORITY
    assert provider_registry.DEFAULT_AUTO_ALLOW["example-fixture"] is False
    assert routing._provider_auto_allowed("example-fixture", {}) is False

    result = search.run_search_request(
        query="SDK fixture", provider="example-fixture", config=config
    )
    assert result["provider"] == "example-fixture"
    assert result["results"][0]["url"] == "https://example.invalid/wsp-sdk-fixture"

    parser = search.build_parser(config)
    provider_action = next(
        action for action in parser._actions if "--provider" in action.option_strings
    )
    assert "example-fixture" in provider_action.choices

    report = search._build_doctor_report(config)
    doctor = {item["provider"]: item for item in report["providers"]}
    assert doctor["example-fixture"]["search_capable"] is True
    print("FIXTURE_PROBE_OK")


if __name__ == "__main__":
    main()
