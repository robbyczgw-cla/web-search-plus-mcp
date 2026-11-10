"""MCP setup uses the same presets as missing-key guidance and routing."""

import json

import pytest

from web_search_plus_mcp import server
from web_search_plus_mcp.provider_registry import PROVIDER_SPECS, SETUP_PRESETS, preset_env_vars
from web_search_plus_mcp.routing import INTENT_FIRST_PROVIDER, MEASURED_PROVIDER_ORDER


@pytest.mark.parametrize("preset", ["starter", "lean", "search", "extract", "all"])
@pytest.mark.parametrize("jev_args,extra", [
    ([], []),
    (["--jev"], ["TYPESAFE_API_KEY"]),
    (["--jev", "--jev-key-file", "/tmp/md/jev/key"], ["TYPESAFE_API_KEY_FILE"]),
])
def test_setup_keys_and_snippet_match_registry(preset, jev_args, extra, tmp_path, capsys):
    assert server.cli_main([
        "setup", "--preset", preset, "--env-file", str(tmp_path / ".env"),
        "--dry-run", "--json", *jev_args,
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    expected = (
        [spec.env_var for spec in PROVIDER_SPECS.values()]
        if preset == "all" else preset_env_vars(preset)
    ) + extra
    assert payload["keys"] == expected
    assert list(payload["snippet"]["mcpServers"]["web-search-plus"]["env"]) == expected
    assert not (tmp_path / ".env").exists()


def test_minimal_is_an_unlisted_lean_alias(tmp_path, capsys):
    assert server.cli_main([
        "setup", "--preset", "minimal", "--env-file", str(tmp_path / ".env"),
        "--dry-run", "--json",
    ]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["keys"] == preset_env_vars("lean")
    assert captured.err == "Preset 'minimal' is an alias for 'lean'; using 'lean'.\n"
    assert server.cli_main(["list", "presets"]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in listed] == ["starter", "lean", "search", "extract", "all"]
    for line in listed[:-1]:
        name, keys = line.split(": ")
        assert keys.split(", ") == preset_env_vars(name)


def test_self_hosted_is_not_offered_until_setup_can_write_the_profile():
    with pytest.raises(SystemExit) as caught:
        server.cli_main(["setup", "--preset", "self-hosted", "--dry-run"])
    assert caught.value.code == 2


def test_starter_preset_matches_the_router_first_providers():
    router_first = set(INTENT_FIRST_PROVIDER.values()) | {MEASURED_PROVIDER_ORDER[0]}
    assert router_first <= set(SETUP_PRESETS["starter"])
