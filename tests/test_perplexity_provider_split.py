import pytest

import web_search_plus_mcp.providers as providers
import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server
from web_search_plus_mcp import config as runtime_config
from web_search_plus_mcp.provider_registry import EXTRACT_PROVIDER_IDS, PROVIDER_SPECS


RETIRED = {"perplexity", "kilo-perplexity"}


def test_answer_only_providers_are_not_mcp_search_capabilities():
    assert RETIRED.isdisjoint(server.SEARCH_PROVIDERS)
    assert RETIRED.isdisjoint(search.SEARCH_PROVIDER_IDS)
    assert RETIRED.isdisjoint(PROVIDER_SPECS)
    assert not hasattr(providers, "search_perplexity")


def test_retired_providers_have_no_freshness_or_extract_metadata():
    assert RETIRED.isdisjoint(providers.PROVIDER_FRESHNESS_FORMATS)
    assert all(not providers.provider_supports_freshness(provider) for provider in RETIRED)
    assert set(EXTRACT_PROVIDER_IDS) == {
        provider for provider, spec in PROVIDER_SPECS.items() if spec.supports_extract
    }


@pytest.mark.parametrize("provider", sorted(RETIRED))
def test_retired_provider_is_rejected_as_explicit_choice(provider):
    from web_search_plus_mcp.request_gate_v3 import validate_provider_mode

    with pytest.raises(Exception):
        validate_provider_mode(provider, "search")


def test_retired_providers_never_enter_auto_routing(monkeypatch):
    monkeypatch.setattr(search, "get_api_key", lambda provider, config=None: "test-key")
    config = runtime_config._deepcopy_default_config()
    config["auto_routing"]["auto_allow"] = {provider: True for provider in search.SEARCH_PROVIDER_IDS}
    config["auto_routing"]["auto_allow"].update({"perplexity": True, "kilo-perplexity": True})

    routing = search.auto_route_provider("current AI search provider comparison", config)
    explanation = search.explain_routing("current AI search provider comparison", config)

    assert routing["provider"] not in RETIRED
    assert RETIRED.isdisjoint(explanation["available_providers"])
