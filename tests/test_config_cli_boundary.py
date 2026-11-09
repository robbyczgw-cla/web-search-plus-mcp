"""Real CLI writes and MCP stdio reads must agree on persisted policy."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from web_search_plus_mcp import config as engine, server


@pytest.fixture
def cli_env(tmp_path):
    return {
        "PATH": str(Path(sys.executable).parent),
        "HOME": str(tmp_path),
        "HERMES_HOME": str(tmp_path / "profile"),
        "WEB_SEARCH_PLUS_CONFIG": str(tmp_path / "config.json"),
        "WSP_CACHE_DIR": str(tmp_path / "cache"),
        "WSP_FORCE_SUBPROCESS": "0",
    }


def cli(env, *args):
    return subprocess.run(
        [sys.executable, "-m", "web_search_plus_mcp.server", *args],
        env=env, cwd=env["HOME"], capture_output=True, text=True, timeout=30,
    )


def runtime(env):
    proc = subprocess.run(
        [sys.executable, "-c", "import json; from web_search_plus_mcp.config import load_config; print(json.dumps(load_config()))"],
        env=env, cwd=env["HOME"], capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def stdio(env, provider="serper"):
    async def call():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "web_search_plus_mcp.server", "serve"],
            env=env, cwd=env["HOME"],
        )
        async with Client(stdio_client(params), read_timeout_seconds=20) as client:
            result = await client.call_tool("web_search", {
                "query": "configuration policy probe", "provider": provider, "detail": "full",
            })
            assert result.is_error
            return result.content[0].text
    return asyncio.run(call())


@pytest.mark.parametrize("seed,command", [
    ({"auto_routing": {"disabled_providers": ["serper"]}}, ["set-routing", "off"]),
    ({"auto_routing": {"enabled": False}}, ["disable", "serper"]),
    ({"auto_routing": {"disabled_providers": ["serper"]}}, ["set-default", "serper"]),
    ({"auto_routing": {"enabled": False, "disabled_providers": ["serper"]}}, ["set-priority", "brave,serper"]),
    ({"auto_routing": {"enabled": False, "disabled_providers": ["serper"]}}, ["set-threshold", "0.7"]),
    ({"mcp": {"detail": "bogus"}, "auto_routing": {"disabled_providers": ["serper"]}}, ["set-threshold", "0.4"]),
    ({"parallel": {"mode": "bogus"}, "auto_routing": {"disabled_providers": ["serper"]}}, ["set-threshold", "0.4"]),
])
def test_invalid_cli_candidate_is_rejected_without_policy_loss(cli_env, seed, command):
    path = Path(cli_env["WEB_SEARCH_PLUS_CONFIG"])
    original = json.dumps(seed)
    path.write_text(original)
    proc = cli(cli_env, "config", *command)
    assert proc.returncode != 0, proc.stdout
    assert "config" in proc.stderr.lower()
    assert "Traceback" not in proc.stderr
    assert path.read_text() == original
    assert list(path.parent.glob("config.json.*")) == []


def test_cli_then_real_stdio_preserves_disabled_policy(cli_env):
    path = Path(cli_env["WEB_SEARCH_PLUS_CONFIG"])
    path.write_text(json.dumps({"defaults": {"max_results": 2}, "auto_routing": {"disabled_providers": ["serper"]}}))
    proc = cli(cli_env, "config", "set-routing", "off")
    payload = json.loads(stdio(cli_env, "tinyfish"))
    print(f"CLI exit={proc.returncode}; config retained={path.exists()}; MCP max_results={payload['limits_applied']['max_results']}")
    assert path.exists(), "MCP call quarantined the CLI output and lost disabled policy"
    assert payload["limits_applied"]["max_results"] == 2
    assert "serper" in runtime(cli_env)["auto_routing"]["disabled_providers"]


def test_set_default_migrates_both_keys_and_reports_effective_provider(cli_env):
    path = Path(cli_env["WEB_SEARCH_PLUS_CONFIG"])
    path.write_text(json.dumps({"default_provider": "brave", "defaults": {"provider": "serper"}}))
    shown = cli(cli_env, "config", "show")
    changed = cli(cli_env, "config", "set-default", "tavily")
    assert changed.returncode == 0, changed.stderr
    # These short fixture keys pass readiness but are rejected before HTTP.
    cli_env.update(BRAVE_API_KEY="test", TAVILY_API_KEY="test")
    payload = json.loads(stdio(cli_env, "auto"))
    assert payload["routing_receipt"]["candidate_order"] == ["tavily"]
    assert json.loads(shown.stdout)["default_provider"] == "brave"
    assert runtime(cli_env)["default_provider"] == "tavily"
    saved = json.loads(path.read_text())
    assert saved["defaults"]["provider"] == saved["default_provider"] == "tavily"


def test_tilde_cli_config_is_used_by_real_stdio(cli_env):
    cli_env["WEB_SEARCH_PLUS_CONFIG"] = "~/config.json"
    (Path(cli_env["HOME"]) / "config.json").write_text(json.dumps({"defaults": {"max_results": 2}}))
    assert cli(cli_env, "config", "disable", "serper").returncode == 0
    payload = json.loads(stdio(cli_env, "tinyfish"))
    assert payload["limits_applied"]["max_results"] == 2
    assert "serper" in runtime(cli_env)["auto_routing"]["disabled_providers"]


def test_backups_survive_same_second(tmp_path, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 100)
    path = tmp_path / "config.json"
    for content in ("{first", "{second"):
        path.write_text(content)
        server._load_behavior_config(path, quarantine=True)
    assert {p.read_text() for p in tmp_path.glob("*.broken-*")} == {"{first", "{second"}
    for content in ("{}", '{"defaults": {"provider": "brave"}}'):
        path.write_text(content)
        server._write_behavior_config({}, path, backup=True)
    assert {p.read_text() for p in tmp_path.glob("*.bak-*")} == {"{}", '{"defaults": {"provider": "brave"}}'}


def test_setup_reports_actual_env_paths_and_does_not_read_cwd(cli_env):
    path = Path(cli_env["HOME"]) / ".env"
    result = cli(cli_env, "setup", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["env_file"] == str(path)
    assert payload["env_file_auto_loaded"] is False
    expected = str(Path(cli_env["HERMES_HOME"]) / ".env")
    assert expected in payload["server_env_files"]
    assert "not automatically" in payload["snippet"]["note"]
    path.write_text("TINYFISH_API_KEY=fixture-cwd-key-must-not-load\n")
    assert "Missing API key" in stdio(cli_env, "tinyfish")


def test_priority_and_threshold_cli_explain_effect(cli_env):
    result = cli(cli_env, "config", "set-priority", "serper,brave")
    assert result.returncode == 0
    assert runtime(cli_env)["auto_routing"]["order"] == "custom"
    result = cli(cli_env, "config", "set-threshold", "0.7")
    assert result.returncode == 0
    assert "no effect" in result.stderr.lower()


@pytest.mark.parametrize("value", [[], ["x"], None, 3, {"defaults": []}])
def test_engine_recovers_wrong_json_shape(tmp_path, monkeypatch, value):
    path = tmp_path / "config.json"
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))
    path.write_text(json.dumps(value))
    engine.load_config()
    assert not path.exists()
    assert len(list(tmp_path.glob("*.broken-*"))) == 1


@pytest.mark.parametrize("raw_config", [
    "[]",
    '{"mcp": {"detail": []}}',
    '{"defaults": []}',
    '{"auto_routing": {"confidence_threshold": {}}}',
    '{"auto_routing": {"confidence_threshold": ' + "9" * 1000 + "}}",
    "[" * 1100 + "0" + "]" * 1100,
])
def test_status_reports_invalid_config_without_moving_or_rewriting_it(tmp_path, monkeypatch, capsys, raw_config):
    path = tmp_path / "config.json"
    path.write_text(raw_config)
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))

    server.cli_main(["status", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["config_warning"].startswith("Invalid config ignored by the MCP server settings: ")
    assert payload["default_provider"] == "serper"
    assert payload["routing_preferences"]["disabled_providers"] == []
    assert payload["tools_if_started_now"] == ["web_search", "web_extract"]
    assert path.read_text() == raw_config
    assert list(tmp_path.glob("config.json.*")) == []
