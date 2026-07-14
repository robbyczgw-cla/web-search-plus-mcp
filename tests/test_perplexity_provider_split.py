import pytest

import web_search_plus_mcp.providers as providers
import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server
from web_search_plus_mcp.provider_registry import EXTRACT_PROVIDER_IDS, PROVIDER_SPECS


RETIRED = {"perplexity", "kilo-perplexity"}


def test_answer_only_providers_are_not_mcp_search_capabilities():
    assert RETIRED.isdisjoint(server.SEARCH_PROVIDERS)
    assert RETIRED.isdisjoint(search.SEARCH_PROVIDER_IDS)
    assert search.PROVIDER_SPECS["perplexity"].supports_search is False
    assert search.PROVIDER_SPECS["kilo-perplexity"].supports_search is False


def test_retired_providers_have_no_freshness_or_extract_metadata():
    assert RETIRED.isdisjoint(providers.PROVIDER_FRESHNESS_FORMATS)
    assert all(
        not providers.provider_supports_freshness(provider)
        for provider in RETIRED
    )
    assert set(EXTRACT_PROVIDER_IDS) == {
        provider
        for provider, spec in PROVIDER_SPECS.items()
        if spec.supports_extract
    }


@pytest.mark.parametrize("provider", ["perplexity", "kilo-perplexity"])
def test_answer_only_provider_stubs_fail_before_network(monkeypatch, provider):
    called = False

    def fake_request(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be reached")

    monkeypatch.setattr(search, "make_request", fake_request)
    with pytest.raises(ValueError, match="no_verified_source_only_endpoint"):
        search.search_perplexity(
            query="latest ai news",
            api_key="retired-test-key",
            provider_name=provider,
        )
    assert called is False


def test_retired_providers_never_enter_auto_routing_scores(monkeypatch):
    monkeypatch.setattr(search, "get_api_key", lambda provider, config=None: "test-key")
    routing = search.QueryAnalyzer(search._deepcopy_default_config()).route(
        "current AI search provider comparison"
    )

    assert RETIRED.isdisjoint(routing["scores"])
    assert RETIRED.isdisjoint(routing["auto_allow_excluded"])


def test_routing_explanation_available_providers_comes_from_source_only_registry(
    monkeypatch,
):
    monkeypatch.setattr(search, "get_api_key", lambda provider, config=None: "test-key")
    config = search._deepcopy_default_config()
    config["auto_routing"]["auto_allow"] = {
        provider: True for provider in search.SEARCH_PROVIDER_IDS
    }
    config["auto_routing"]["auto_allow"].update(
        {"perplexity": True, "kilo-perplexity": True}
    )

    explanation = search.explain_routing("current AI search provider comparison", config)

    assert set(explanation["available_providers"]) == set(search.SEARCH_PROVIDER_IDS)
    assert RETIRED.isdisjoint(explanation["available_providers"])
