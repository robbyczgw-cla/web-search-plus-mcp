from __future__ import annotations

import json

import web_search_plus_mcp.server as server
from web_search_plus_mcp.jev_setup import JEV_DECISIONS, apply_jev_config, parse_decisions, status_payload


def test_parse_decisions_default_is_three():
    assert parse_decisions(None) == JEV_DECISIONS
    assert JEV_DECISIONS == ("search_type", "extract_quality", "language_fill")


def test_status_payload_never_includes_secret():
    payload = status_payload(
        {"TYPESAFE_API_KEY": "apikey_should_not_leak"},
        {"jev": {"enabled": True, "extract_quality": True}},
    )
    blob = json.dumps(payload)
    assert "apikey_should_not_leak" not in blob
    assert payload["key_present"] is True
    assert payload["key_source"] == "env"


def test_apply_jev_config_strips_api_key_field():
    config = apply_jev_config({"jev": {"api_key": "nope"}}, enabled=True, decisions=("search_type",))
    assert "api_key" not in config["jev"]
    assert config["jev"]["search_type"] is True
    assert config["jev"]["extract_quality"] is False


def test_setup_default_dry_run_leaves_jev_off(tmp_path, capsys):
    env_file = tmp_path / ".env"
    assert server.cli_main(["setup", "--preset", "lean", "--env-file", str(env_file), "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["jev"]["enabled"] is False
    assert "TYPESAFE_API_KEY" not in payload["keys"]
    assert "TYPESAFE_API_KEY" not in payload["snippet"]["mcpServers"]["web-search-plus"]["env"]
    assert not env_file.exists()


def test_setup_jev_dry_run_adds_key_slot_without_writing(tmp_path, capsys):
    env_file = tmp_path / ".env"
    assert (
        server.cli_main(
            [
                "setup",
                "--preset",
                "lean",
                "--jev",
                "--jev-decisions",
                "extract_quality,search_type",
                "--env-file",
                str(env_file),
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["jev"]["enabled"] is True
    assert payload["jev"]["decisions"] == ["extract_quality", "search_type"]
    assert "TYPESAFE_API_KEY" in payload["keys"]
    assert payload["snippet"]["mcpServers"]["web-search-plus"]["env"]["TYPESAFE_API_KEY"] == "your_typesafe_key"
    assert not env_file.exists()


def test_setup_jev_writes_env_and_config_without_secret(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env"
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(server.CONFIG_ENV_VAR, str(config_path))
    secret = tmp_path / "key"
    secret.write_text("file-only-secret\n", encoding="utf-8")
    assert (
        server.cli_main(
            [
                "setup",
                "--preset",
                "lean",
                "--jev",
                "--jev-key-file",
                str(secret),
                "--jev-decisions",
                "search_type,language_fill",
                "--env-file",
                str(env_file),
                "--config-path",
                str(config_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "file-only-secret" not in out
    env_text = env_file.read_text(encoding="utf-8")
    assert "TYPESAFE_API_KEY_FILE=" in env_text
    assert str(secret) in env_text
    assert "file-only-secret" not in env_text
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["jev"]["enabled"] is True
    assert saved["jev"]["search_type"] is True
    assert saved["jev"]["language_fill"] is True
    assert saved["jev"]["extract_quality"] is False
    assert "api_key" not in saved["jev"]
    assert "TYPESAFE_API_KEY_FILE" in out
    assert "file-only-secret" not in out


def test_status_json_includes_jev_off_by_default(monkeypatch, capsys):
    monkeypatch.setenv("BRAVE_API_KEY", "brv-test")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY_FILE", raising=False)
    assert server.cli_main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["jev"]["enabled"] is False
    assert payload["jev"]["key_present"] is False
    assert "api_key" not in payload["jev"]
    blob = json.dumps(payload)
    assert "brv-test" not in blob or payload["jev"]["key_present"] is False
