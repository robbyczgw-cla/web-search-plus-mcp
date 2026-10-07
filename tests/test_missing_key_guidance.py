from __future__ import annotations

import json

import pytest

from web_search_plus_mcp import config


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for spec in config.PROVIDER_SPECS.values():
        monkeypatch.delenv(spec.env_var, raising=False)
    monkeypatch.delenv("SEARXNG_INSTANCE_URL", raising=False)
    monkeypatch.setattr(config, "get_api_key", lambda provider, cfg=None: None)


def _error(provider):
    with pytest.raises(config.ProviderConfigError) as exc:
        config.validate_api_key(provider, {})
    return json.loads(str(exc.value))


def test_missing_key_hint_points_to_env_not_config_json():
    payload = _error("serper")
    hints = " ".join(payload["how_to_fix"])
    assert "config.json" not in hints
    assert "SERPER_API_KEY" in hints
    assert "web-search-plus-mcp setup" in hints
    assert payload["env_var"] == "SERPER_API_KEY"


def test_missing_searxng_hint_uses_env_var():
    hints = " ".join(_error("searxng")["how_to_fix"])
    assert "config.json" not in hints
    assert "SEARXNG_INSTANCE_URL" in hints
