"""auto_routing.enabled is read once, at the config boundary."""
import json

import pytest

from web_search_plus_mcp import config, routing


@pytest.mark.parametrize("value,enabled", [(0, False), ("false", False), ("off", False), (1, True), ("on", True), (False, False)])
def test_routing_switch_has_one_reading(tmp_path, monkeypatch, value, enabled):
    # 0 or "false" kept auto routing on in the engine (it tested `is False`),
    # while the MCP status read them as off.
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"default_provider": "brave", "auto_routing": {"enabled": value}}))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))
    loaded = config.load_config()
    assert loaded["auto_routing"]["enabled"] is enabled
    reason = routing.auto_route_provider("python asyncio", loaded)["reason"]
    assert (reason == "auto_routing_disabled_default_provider") is not enabled


def test_routing_switch_that_is_neither_on_nor_off_is_an_invalid_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"auto_routing": {"enabled": "maybe"}}))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))
    assert config.load_config()["auto_routing"]["enabled"] is True
    assert not path.exists() and len(list(tmp_path.glob("config.json.broken-*"))) == 1


def test_cli_edit_keeps_a_switch_written_as_text(tmp_path, monkeypatch, capsys):
    # The MCP config CLI read "false" with bool() and wrote back true: one
    # unrelated edit turned auto routing on again.
    from web_search_plus_mcp import server

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"auto_routing": {"enabled": "false"}}))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(path))
    assert server.cli_main(["config", "disable", "brave"]) == 0
    capsys.readouterr()
    assert json.loads(path.read_text())["auto_routing"]["enabled"] is False
    assert config.load_config()["auto_routing"]["enabled"] is False
