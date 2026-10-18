"""The credentials layer reads the process environment unless a host installs a resolver."""
from web_search_plus_mcp import credentials
from web_search_plus_mcp.config import get_api_key, get_searxng_instance_url


def test_without_a_resolver_get_secret_reads_the_process_environment(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    assert credentials.get_secret_resolver() is None
    assert credentials.file_credentials_allowed() is True
    assert credentials.get_secret("SERPER_API_KEY") == "test-key"
    assert credentials.get_secret("NOT_SET_ANYWHERE", "fallback") == "fallback"


def test_config_json_key_wins_over_the_environment_without_a_resolver(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "env-key")
    assert get_api_key("serper", {"serper": {"api_key": "file-key"}}) == "file-key"
    assert get_api_key("serper", {}) == "env-key"


def test_an_installed_resolver_owns_credentials_and_ignores_config_json(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "env-key")
    credentials.set_secret_resolver(lambda name, default=None: "resolver-key" if name == "SERPER_API_KEY" else default)
    assert credentials.file_credentials_allowed() is False
    assert get_api_key("serper", {"serper": {"api_key": "file-key"}}) == "resolver-key"


def test_searxng_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SEARXNG_INSTANCE_URL", "https://93.184.216.34")
    assert get_searxng_instance_url({}) == "https://93.184.216.34"


def test_redact_secrets_and_urls():
    redacted = credentials.redact_secrets({
        "serper": {"api_key": "test-key", "x-api-key": "other"},
        "searxng": {"base_url": "https://user:pw@searx.example.org/path?token=abc"},
        "keyless": True,
    })
    assert redacted["serper"] == {"api_key": "set", "x-api-key": "set"}
    assert redacted["searxng"]["base_url"] == "https://searx.example.org/path"
    assert redacted["keyless"] is True
    assert credentials.redact_url("https://u:p@h.example:8080/p?q=1", origin_only=True) == "https://h.example:8080"
