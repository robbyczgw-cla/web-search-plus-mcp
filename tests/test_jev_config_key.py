"""A Jev credential in config.json is never read; it is named, settings stay."""
import json

from web_search_plus_mcp import config


def test_jev_key_file_in_config_is_named_once_and_keeps_settings(tmp_path, monkeypatch, caplog):
    # jev.api_key_file in config.json was accepted silently but never read:
    # Jev ran without a key and nothing said why.
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"default_provider": "brave", "jev": {"api_key_file": str(tmp_path / "k"), "enabled": True}}))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))
    monkeypatch.setattr(config, "_IGNORED_FILE_KEY_WARNED", set())
    with caplog.at_level("WARNING"):
        for _ in range(2):
            loaded = config.load_config()
            assert loaded["default_provider"] == "brave" and loaded["jev"]["enabled"] is True
    assert path.exists()
    assert caplog.text.count("config.json contains an API key for jev") == 1
    assert "TYPESAFE_API_KEY" in caplog.text
