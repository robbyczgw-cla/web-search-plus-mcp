import json

import pytest

import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server


def test_native_perplexity_defaults_to_direct_api_and_key(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
    monkeypatch.setenv("KILOCODE_API_KEY", "kilo-test-key")

    assert search._canonical_provider("perplexity") == "perplexity"
    assert search.DEFAULT_CONFIG["perplexity"]["api_url"] == "https://api.perplexity.ai/chat/completions"
    assert search.DEFAULT_CONFIG["perplexity"]["model"] == "sonar-pro"
    assert search.get_api_key("perplexity") == "pplx-test-key"


def test_kilo_perplexity_is_distinct_provider_and_underscore_alias(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
    monkeypatch.setenv("KILOCODE_API_KEY", "kilo-test-key")

    assert search._canonical_provider("kilo_perplexity") == "kilo-perplexity"
    assert search._canonical_provider("kilo-perplexity") == "kilo-perplexity"
    assert search._canonical_provider("kilo-perplexity") != "perplexity"
    assert "kilo-perplexity" in search._VALID_PROVIDERS
    assert search.DEFAULT_CONFIG["kilo-perplexity"]["api_url"] == "https://api.kilo.ai/api/gateway/chat/completions"
    assert search.DEFAULT_CONFIG["kilo-perplexity"]["model"] == "perplexity/sonar-pro"
    assert search.get_api_key("kilo-perplexity") == "kilo-test-key"


def test_missing_perplexity_keys_report_the_right_env_var(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("KILOCODE_API_KEY", raising=False)

    with pytest.raises(search.ProviderConfigError) as native_exc:
        search.validate_api_key("perplexity")
    native_payload = json.loads(str(native_exc.value))
    assert native_payload["env_var"] == "PERPLEXITY_API_KEY"
    assert native_payload["provider"] == "perplexity"

    with pytest.raises(search.ProviderConfigError) as kilo_exc:
        search.validate_api_key("kilo-perplexity")
    kilo_payload = json.loads(str(kilo_exc.value))
    assert kilo_payload["env_var"] == "KILOCODE_API_KEY"
    assert kilo_payload["provider"] == "kilo-perplexity"


def test_perplexity_search_function_uses_native_defaults(monkeypatch):
    captured = {}

    def fake_request(api_url, headers, body):
        captured["api_url"] = api_url
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": "answer"}}], "citations": []}

    monkeypatch.setattr(search, "make_request", fake_request)
    result = search.search_perplexity("what changed", "pplx-test-key")

    assert captured["api_url"] == "https://api.perplexity.ai/chat/completions"
    assert captured["body"]["model"] == "sonar-pro"
    assert captured["headers"]["Authorization"] == "Bearer pplx-test-key"
    assert result["provider"] == "perplexity"


def test_server_metadata_keeps_kilo_perplexity_distinct():
    assert server._canonical_provider("kilo_perplexity") == "kilo-perplexity"
    assert server._canonical_provider("kilo-perplexity") == "kilo-perplexity"
    assert server._canonical_provider("kilo-perplexity") != "perplexity"
    assert server.SEARCH_PROVIDERS["perplexity"]["env"] == "PERPLEXITY_API_KEY"
    assert server.SEARCH_PROVIDERS["kilo-perplexity"]["env"] == "KILOCODE_API_KEY"


def test_auto_routing_prefers_native_perplexity_when_both_keys_are_set(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
    monkeypatch.setenv("KILOCODE_API_KEY", "kilo-test-key")

    config = search.DEFAULT_CONFIG.copy()
    config["auto_routing"] = {
        **search.DEFAULT_CONFIG["auto_routing"],
        "disabled_providers": [
            "serper",
            "brave",
            "tavily",
            "linkup",
            "querit",
            "exa",
            "firecrawl",
            "you",
            "searxng",
        ],
        "auto_allow": {
            **search.DEFAULT_CONFIG["auto_routing"]["auto_allow"],
            "perplexity": True,
            "kilo-perplexity": True,
        },
    }
    routing = search.auto_route_provider("what is the current status of SpaceX", config)

    assert routing["provider"] == "perplexity"
    assert routing["scores"]["perplexity"] >= routing["scores"]["kilo-perplexity"]


def test_cache_key_keeps_native_and_kilo_perplexity_separate():
    native_key = search._get_cache_key("same query", "perplexity", 5)
    kilo_key = search._get_cache_key("same query", "kilo-perplexity", 5)

    assert native_key != kilo_key
