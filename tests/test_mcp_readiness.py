"""MCP status, .env loading and the engine give one readiness answer (5.1.7).

Each case starts a fresh interpreter (the .env loaders run at import, like a
real server start) on a copy of the package, so files next to the package and
in $HERMES_HOME are real files. No provider is contacted.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "web_search_plus_mcp"

PROBE = r"""
import json, sys
from web_search_plus_mcp import server, config
status = server._status_payload()
cfg = config.load_config()
out = {
    "status": {name: {k: status["providers"][name].get(k) for k in ("configured", "state", "reason_code", "source")}
               for name in ("brave", "keenable", "searxng")},
    "search_configured": status["search_configured"],
    "engine": {name: config.provider_configured(name, cfg) for name in ("brave", "keenable", "searxng")},
    "brave_key_is_real": config.get_api_key("brave", cfg) == "brave-real-key-from-profile",
}
print(json.dumps(out))
"""


def _run(tmp_path, *, package_env=None, profile_env=None, config=None, extra_env=None):
    root = tmp_path / "install"
    shutil.copytree(PACKAGE, root / "web_search_plus_mcp", ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "hermes"
    home.mkdir()
    if package_env is not None:
        (root / ".env").write_text(package_env)
    if profile_env is not None:
        (home / ".env").write_text(profile_env)
    config_path = tmp_path / "config.json"
    if config is not None:
        config_path.write_text(json.dumps(config))
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HERMES_HOME": str(home),
        "WSP_CACHE_DIR": str(tmp_path / "cache"), "WEB_SEARCH_PLUS_CONFIG": str(config_path),
        "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1", **(extra_env or {}),
    }
    proc = subprocess.run([sys.executable, "-c", PROBE], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_placeholder_next_to_the_package_no_longer_hides_the_real_profile_key(tmp_path):
    # 5.1.6: the raw loader set BRAVE_API_KEY=your_brave_key first; the real key
    # in $HERMES_HOME/.env was then skipped, status said configured, the engine
    # said "Missing API key for brave".
    out = _run(tmp_path, package_env="BRAVE_API_KEY=your_brave_key\nEXA_API_KEY=\n",
               profile_env="BRAVE_API_KEY=brave-real-key-from-profile\n")
    assert out["brave_key_is_real"] is True
    assert out["status"]["brave"] == {"configured": True, "state": "ready", "reason_code": "ready", "source": "environment"}
    assert out["engine"]["brave"] is True


def test_status_and_engine_agree_on_keyless_and_placeholders(tmp_path):
    out = _run(tmp_path, config={"keenable": {"allow_public": True}},
               extra_env={"BRAVE_API_KEY": "your_brave_key"})
    # keenable: opted in via config.json, which the MCP host reads (5.1.6 status: not configured)
    assert out["status"]["keenable"]["configured"] is True and out["engine"]["keenable"] is True
    # brave: a template placeholder (5.1.6 status: configured; engine: missing)
    assert out["status"]["brave"]["configured"] is False and out["engine"]["brave"] is False
    assert out["status"]["brave"]["reason_code"] == "placeholder_value"
    assert out["search_configured"] is True


def test_private_searxng_url_is_not_reported_configured(tmp_path):
    out = _run(tmp_path, extra_env={"SEARXNG_INSTANCE_URL": "http://127.0.0.1:8888"})
    assert out["status"]["searxng"]["configured"] is False
    assert out["status"]["searxng"]["reason_code"] == "searxng_url_private"
    assert out["engine"]["searxng"] is False


@pytest.mark.parametrize("value", ["", "   ", "FULL", "verbose"])
def test_detail_env_value_never_breaks_the_tools(monkeypatch, tmp_path, value):
    from web_search_plus_mcp import server

    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv(server.DETAIL_ENV_VAR, value)
    for name in ("SERPER_API_KEY", "BRAVE_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    text = asyncio.run(server.call_tool("web_search", {"query": "x", "provider": "serper"}))[0].text
    payload = json.loads(text)

    # 5.1.6: ValueError on every call. Now the call runs; FULL means full.
    assert payload["status"] == "failed"
    expected = "full" if value.strip().lower() == "full" else "compact"
    assert (payload.get("detail") or "full") == expected


def test_compact_and_v3_name_the_setup_problem_not_the_serper_filler(monkeypatch, tmp_path):
    # 5.1.6: "Missing API key for serper" plus Serper signup steps for a user
    # whose Brave key was still the template placeholder.
    from jsonschema import Draft202012Validator
    from web_search_plus_mcp import search, server

    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("BRAVE_API_KEY", "your_brave_key")
    for name in ("SERPER_API_KEY", server.DETAIL_ENV_VAR):
        monkeypatch.delenv(name, raising=False)

    compact = json.loads(asyncio.run(server.call_tool("web_search", {"query": "python release notes"}))[0].text)
    assert compact["status"] == "failed"
    assert compact["error"].startswith("BRAVE_API_KEY still holds a template placeholder")
    assert compact["how_to_fix"] == ["set BRAVE_API_KEY=<real value> in the MCP client's env block or the server's .env"]
    # Nothing from the serper filler attempt the user never chose.
    assert compact.get("env_var") != "SERPER_API_KEY"
    assert "provider_errors" not in compact
    assert "fallback_from" not in compact.get("routing", {})

    payload, _code = search.run_cli_contract_v3(["--contract-v3", "--query", "python release notes", "--no-cache"])
    error = payload["error"]
    assert (error["error_class"], error["retryable"]) == ("config", False)
    assert error["details"]["readiness"][0]["reason_code"] == "placeholder_value"
    assert "provider" not in error and "env_var" not in error["details"]
    schema = json.loads((PACKAGE.parent / "schemas/v3/response.schema.json").read_text())
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []



def test_invalid_detail_environment_warns_once_and_keeps_argument_precedence(tmp_path, monkeypatch, capsys):
    from web_search_plus_mcp import server

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"mcp": {"detail": "full"}}))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(config_path))
    monkeypatch.setenv("WEB_SEARCH_PLUS_MCP_DETAIL", " verbose ")
    monkeypatch.setattr(server, "_DETAIL_ENV_WARNED", False)

    async def fake_run(*args, **kwargs):
        return {"contract_version": "3.0", "status": "ok", "results": []}

    monkeypatch.setattr(server, "_run_subprocess", fake_run)
    explicit = json.loads(asyncio.run(server.call_tool("web_search", {"query": "q", "detail": "compact"}))[0].text)
    assert explicit["detail"] == "compact"
    assert capsys.readouterr().err == ""
    for _ in range(2):
        configured = json.loads(asyncio.run(server.call_tool("web_search", {"query": "q"}))[0].text)
        assert configured["contract_version"] == "3.0"
        assert "detail" not in configured
    assert capsys.readouterr().err == json.dumps({
        "warning": "WEB_SEARCH_PLUS_MCP_DETAIL must be compact or full; ignoring it",
    }) + "\n"


@pytest.mark.parametrize("config,call", [
    ({}, "status"),
    ({}, ("web_search", {"query": "q"})),
    ({}, ("web_search", {"query": "q", "provider": "brave"})),
    ({}, ("web_search", {"query": "q", "provider": "searxng"})),
    ({}, ("web_extract", {"urls": ["https://example.com"]})),
    ({"profile": "self_hosted"}, ("web_search", {"query": "q"})),
], ids=["status", "auto", "explicit-brave", "explicit-searxng", "extract", "self-hosted"])
def test_every_recommended_cli_command_is_one_the_mcp_cli_accepts(config, call, monkeypatch, tmp_path, capsys):
    # 5.1.7 recommended "web-search-plus-mcp setup brave" and
    # "setup --preset extract"; the MCP CLI rejected both with exit 2.
    import shlex
    from web_search_plus_mcp import server

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps(config))
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(tmp_path / "config.json"))
    for meta in server.SEARCH_PROVIDERS.values():
        monkeypatch.delenv(meta["env"], raising=False)
    monkeypatch.delenv("SEARXNG_INSTANCE_URL", raising=False)
    if call == "status":
        out = server._status_payload()
    else:
        out = json.loads(asyncio.run(server.call_tool(call[0], {**call[1], "detail": "full"}))[0].text)

    def strings(obj):
        if isinstance(obj, dict):
            return [s for value in obj.values() for s in strings(value)]
        if isinstance(obj, list):
            return [s for value in obj for s in strings(value)]
        return [obj] if isinstance(obj, str) else []

    commands = {s for s in strings(out) if s.startswith("web-search-plus-mcp ")}
    for command in commands:
        argv = shlex.split(command)[1:]
        assert server.cli_main(argv + (["--dry-run"] if argv[0] == "setup" else [])) == 0, command
    capsys.readouterr()
