"""Search evidence is scoped to effective provider credentials on both cache paths."""
import json

import pytest

from web_search_plus_mcp import cache, config, credentials, providers, search
from web_search_plus_mcp.compat_v3 import legacy_request_to_v3
from web_search_plus_mcp.contract_v3 import Capability
from web_search_plus_mcp.orchestrator_v3 import ProviderPlan


def resolver(values):
    return lambda name, default=None: values.get(name, default)


@pytest.mark.parametrize("provider, env_name, first_value", [("brave", "BRAVE_API_KEY", "profile-a-fixture-credential"), ("searxng", "SEARXNG_INSTANCE_URL", "https://user:fixture-password@example.com/private?token=fixture")])
def test_search_cache_does_not_cross_profile_credentials(monkeypatch, provider, env_name, first_value):
    monkeypatch.setattr(config, "_validate_searxng_url", lambda url: url)
    monkeypatch.setattr(providers, "search_" + provider, lambda **kwargs: {"provider": provider, "query": "private query", "results": [{"title": "Profile A", "url": "https://example.com/a", "snippet": "private evidence"}]})
    settings = config._deepcopy_default_config()
    monkeypatch.setattr(credentials, "_resolver", resolver({env_name: first_value}))
    first = search.run_search_request(query="private query", provider=provider, config=settings)
    assert first["results"] and not first["cached"]
    repeat = search.run_search_request(query="private query", provider=provider, config=settings)
    assert repeat["cached"]
    monkeypatch.setattr(credentials, "_resolver", resolver({}))
    missing = search.run_search_request(query="private query", provider=provider, config=settings)
    assert not missing.get("cached")
    assert not missing.get("results")


def test_legacy_cache_does_not_cross_resolvers(monkeypatch):
    monkeypatch.setattr(credentials, "_resolver", resolver({"BRAVE_API_KEY": "profile-a-fixture-credential"}))
    cache.cache_put("private query", "brave", 1, {"results": ["private evidence"]})
    assert cache.cache_get("private query", "brave", 1)
    monkeypatch.setattr(credentials, "_resolver", resolver({}))
    assert cache.cache_get("private query", "brave", 1) is None
    monkeypatch.setattr(credentials, "_resolver", resolver({"BRAVE_API_KEY": "profile-b-fixture-credential"}))
    assert cache.cache_get("private query", "brave", 1) is None


def test_cache_vary_covers_fallback_keys_and_preserves_keyless_sharing(monkeypatch):
    request = legacy_request_to_v3(Capability.SEARCH, {"query": "q", "provider": "brave"})
    plan = ProviderPlan(("brave", "serper"), "brave")
    monkeypatch.setattr(credentials, "_resolver", resolver({"SERPER_API_KEY": "first-fixture-key"}))
    first = search._search_cache_vary(request, plan, {})
    monkeypatch.setattr(credentials, "_resolver", resolver({"SERPER_API_KEY": "second-fixture-key"}))
    second = search._search_cache_vary(request, plan, {})
    assert first != second
    assert "fixture-key" not in json.dumps([first, second])
    keyless = ProviderPlan(("keenable",), "keenable")
    monkeypatch.setattr(credentials, "_resolver", resolver({"KEENABLE_ALLOW_PUBLIC": "true"}))
    shared = search._search_cache_vary(request, keyless, {})
    monkeypatch.setattr(credentials, "_resolver", resolver({"KEENABLE_ALLOW_PUBLIC": "true", "BRAVE_API_KEY": "unrelated-fixture-key"}))
    assert search._search_cache_vary(request, keyless, {}) == shared
    monkeypatch.setattr(credentials, "_resolver", resolver({}))
    assert search._search_cache_vary(request, keyless, {}) != shared
