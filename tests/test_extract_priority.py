import pytest

from web_search_plus_mcp import config as runtime_config
from web_search_plus_mcp import extract


DEFAULT_EXTRACT_ORDER = [
    "tavily",
    "exa",
    "linkup",
    "parallel",
    "firecrawl",
    "you",
    "keenable",
    "serper",
    "hound",
]


def test_default_extract_priority_stays_registry_order():
    assert runtime_config.DEFAULT_CONFIG["auto_routing"]["extract_provider_priority"] == DEFAULT_EXTRACT_ORDER
    assert extract.resolve_extract_provider_priority({}) == DEFAULT_EXTRACT_ORDER


def test_partial_extract_priority_is_completed_in_registry_order():
    config = runtime_config._deepcopy_default_config()
    config["auto_routing"]["extract_provider_priority"] = ["serper", "parallel"]

    normalized = runtime_config._validate_runtime_config(config)

    assert normalized["auto_routing"]["extract_provider_priority"] == [
        "serper",
        "parallel",
        "tavily",
        "exa",
        "linkup",
        "firecrawl",
        "you",
        "keenable",
        "hound",
    ]


def test_extract_priority_rejects_search_only_provider():
    config = runtime_config._deepcopy_default_config()
    config["auto_routing"]["extract_provider_priority"] = ["serper", "brave"]

    with pytest.raises(ValueError, match="does not support extraction"):
        runtime_config._validate_runtime_config(config)


def test_auto_extract_honors_configured_extract_priority(monkeypatch):
    calls = []
    config = {
        "auto_routing": {
            "extract_provider_priority": ["serper", "parallel"],
            "disabled_providers": [],
        }
    }
    monkeypatch.setattr(extract, "_validate_extract_urls", lambda urls, config: urls)
    monkeypatch.setattr(extract, "get_api_key", lambda provider, config: f"{provider}-key")
    monkeypatch.setattr(extract, "keyless_public_allowed", lambda provider, config: False)
    monkeypatch.setattr(extract, "provider_in_cooldown", lambda provider: (False, 0))
    monkeypatch.setattr(extract, "execute_provider_with_retry", lambda provider, fn: fn())
    monkeypatch.setattr(extract, "reset_provider_health", lambda provider: None)

    def fake_serper(*args, **kwargs):
        calls.append("serper")
        return {"provider": "serper", "results": [{"url": "https://example.com", "content": "ok"}]}

    monkeypatch.setattr(extract, "extract_serper", fake_serper)
    monkeypatch.setattr(extract, "extract_parallel", lambda *args, **kwargs: pytest.fail("parallel should not run"))

    result = extract.extract_plus(["https://example.com"], provider="auto", config=config)

    assert calls == ["serper"]
    assert result["provider"] == "serper"
    assert result["routing"]["provider"] == "serper"
    assert result["routing"]["requested_provider"] == "auto"
    assert result["routing"]["fallback_used"] is False


def test_explicit_extract_provider_stays_first(monkeypatch):
    calls = []
    config = {
        "auto_routing": {
            "extract_provider_priority": ["tavily", "serper"],
            "disabled_providers": [],
        }
    }
    monkeypatch.setattr(extract, "_validate_extract_urls", lambda urls, config: urls)
    monkeypatch.setattr(extract, "get_api_key", lambda provider, config: f"{provider}-key")
    monkeypatch.setattr(extract, "keyless_public_allowed", lambda provider, config: False)
    monkeypatch.setattr(extract, "provider_in_cooldown", lambda provider: (False, 0))
    monkeypatch.setattr(extract, "execute_provider_with_retry", lambda provider, fn: fn())
    monkeypatch.setattr(extract, "reset_provider_health", lambda provider: None)

    def fake_serper(*args, **kwargs):
        calls.append("serper")
        return {"provider": "serper", "results": [{"url": "https://example.com", "content": "ok"}]}

    monkeypatch.setattr(extract, "extract_serper", fake_serper)
    monkeypatch.setattr(extract, "extract_tavily", lambda *args, **kwargs: pytest.fail("tavily should not run"))

    result = extract.extract_plus(["https://example.com"], provider="serper", config=config)

    assert calls == ["serper"]
    assert result["provider"] == "serper"
    assert result["routing"]["requested_provider"] == "serper"
