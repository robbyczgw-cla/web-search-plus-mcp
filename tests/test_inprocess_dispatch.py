"""MCP tool calls run search.py in-process by default, with subprocess parity."""
from __future__ import annotations

import asyncio
import json
import time

import pytest

from web_search_plus_mcp import search, server

pytestmark = pytest.mark.inprocess


def _call(name, arguments):
    return json.loads(asyncio.run(server.call_tool(name, arguments))[0].text)


def _no_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("in-process dispatch must not spawn search.py")

    monkeypatch.setattr(server.subprocess, "run", forbidden)


def _capture_argv(monkeypatch, payload=None):
    seen = {}

    def fake(argv, *, config=None):
        seen["argv"] = list(argv)
        return (payload if payload is not None else {"contract_version": "3.0", "status": "ok", "results": []}), 0

    monkeypatch.setattr(search, "run_cli_contract_v3", fake)
    return seen


def test_search_runs_in_process_with_cli_argv(monkeypatch):
    _no_subprocess(monkeypatch)
    seen = _capture_argv(monkeypatch)
    _call("web_search", {"query": "--looks-like-a-flag", "provider": "serper", "count": 3, "freshness": "week"})
    argv = seen["argv"]
    assert argv[0] == "--query=--looks-like-a-flag"
    assert argv[argv.index("--provider") + 1] == "serper"
    assert argv[argv.index("--max-results") + 1] == "3"
    assert "--contract-v3" in argv and "--compact" in argv
    assert argv[argv.index("--freshness") + 1] == "week"


def test_omitted_count_leaves_max_results_to_config(monkeypatch):
    _no_subprocess(monkeypatch)
    seen = _capture_argv(monkeypatch)
    _call("web_search", {"query": "q"})
    assert "--max-results" not in seen["argv"]


def test_extract_runs_in_process(monkeypatch):
    _no_subprocess(monkeypatch)
    seen = _capture_argv(monkeypatch)
    _call("web_extract", {"urls": ["https://example.com/a"], "provider": "tavily"})
    argv = seen["argv"]
    assert argv[:2] == ["--extract-urls", "https://example.com/a"]
    assert argv[argv.index("--provider") + 1] == "tavily"


def test_real_parser_accepts_server_argv(monkeypatch):
    """The real run_cli_contract_v3 parses the exact argv the server builds."""
    _no_subprocess(monkeypatch)
    seen = {}

    def fake_v3(request, *, config=None):
        seen["request"] = request

        class _Resp:
            def to_dict(self):
                return {"contract_version": "3.0", "status": "ok", "results": []}

        return _Resp()

    monkeypatch.setattr(search, "run_search_request_v3", fake_v3)
    payload = _call("web_search", {"query": "hifi amp", "provider": "exa", "count": 4, "no_cache": True})
    assert payload["status"] == "ok"
    dumped = json.dumps(seen["request"].to_dict() if hasattr(seen["request"], "to_dict") else repr(seen["request"]), default=str)
    assert "hifi amp" in dumped
    assert seen["request"].capability.value == "search"


def test_argparse_error_maps_to_subprocess_failed_payload(monkeypatch):
    _no_subprocess(monkeypatch)

    def bad(argv, *, config=None):
        raise SystemExit(2)

    monkeypatch.setattr(search, "run_cli_contract_v3", bad)
    payload = _call("web_search", {"query": "q", "provider": "serper"})
    assert payload["error_v3"]["code"] == "wsp.subprocess.failed"
    assert payload["error"] == "Web Search Plus subprocess failed."


def test_engine_exception_maps_to_failed_payload_without_leaking(monkeypatch, capsys):
    _no_subprocess(monkeypatch)

    def boom(argv, *, config=None):
        raise RuntimeError("secret-token-abc leaked?")

    monkeypatch.setattr(search, "run_cli_contract_v3", boom)
    payload = _call("web_search", {"query": "q", "provider": "serper"})
    assert payload["error_v3"]["code"] == "wsp.subprocess.failed"
    assert "secret-token-abc" not in json.dumps(payload)
    assert "secret-token-abc" not in capsys.readouterr().err


def test_timeout_maps_to_timeout_payload(monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr(server, "DEFAULT_SEARCH_SUBPROCESS_TIMEOUT_SECONDS", 1)

    def slow(argv, *, config=None):
        time.sleep(3)
        return {"status": "ok"}, 0

    monkeypatch.setattr(search, "run_cli_contract_v3", slow)
    started = time.monotonic()
    payload = _call("web_search", {"query": "q", "provider": "serper"})
    assert time.monotonic() - started < 2.5
    assert payload["error_v3"]["code"] == "wsp.subprocess.timeout"
    assert payload["error_v3"]["retryable"] is True


def test_non_dict_payload_is_invalid_response(monkeypatch):
    _no_subprocess(monkeypatch)
    monkeypatch.setattr(search, "run_cli_contract_v3", lambda argv, *, config=None: (["not", "a", "dict"], 0))
    payload = _call("web_search", {"query": "q", "provider": "serper"})
    assert payload["error_v3"]["code"] == "wsp.subprocess.invalid_response"


def test_unsupported_argv_falls_back_to_subprocess(monkeypatch):
    calls = {}

    def unsupported(argv, *, config=None):
        raise ValueError("run_cli_contract_v3 only supports --contract-v3 search and extract")

    class _Result:
        returncode = 0
        stdout = json.dumps({"status": "ok", "results": [], "via": "subprocess"})
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(search, "run_cli_contract_v3", unsupported)
    monkeypatch.setattr(server.subprocess, "run", fake_run)
    payload = _call("web_search", {"query": "q", "provider": "serper"})
    assert payload["via"] == "subprocess"
    assert calls["cmd"][1] == str(server.SEARCH_SCRIPT)


def test_force_subprocess_env_restores_old_path(monkeypatch):
    monkeypatch.setenv("WSP_FORCE_SUBPROCESS", "1")
    monkeypatch.setattr(search, "run_cli_contract_v3", lambda *a, **k: pytest.fail("in-process used"))

    class _Result:
        returncode = 0
        stdout = json.dumps({"status": "ok", "results": []})
        stderr = ""

    monkeypatch.setattr(server.subprocess, "run", lambda cmd, **kw: _Result())
    assert _call("web_search", {"query": "q", "provider": "serper"})["status"] == "ok"


def test_run_cli_contract_v3_rejects_non_v3_modes():
    for argv in (["--query", "q"], ["--cache-stats", "--contract-v3"], ["doctor", "--contract-v3"]):
        with pytest.raises((ValueError, SystemExit)):
            search.run_cli_contract_v3(argv, config=search.load_config())


def test_concurrent_calls_do_not_cross_results(monkeypatch):
    _no_subprocess(monkeypatch)

    def echo(argv, *, config=None):
        query = argv[0].split("=", 1)[1]
        time.sleep(0.05)
        return {"contract_version": "3.0", "status": "ok", "results": [], "echo": query}, 0

    monkeypatch.setattr(search, "run_cli_contract_v3", echo)

    async def many():
        calls = [server.call_tool("web_search", {"query": f"q{i}", "provider": "serper"}) for i in range(20)]
        return await asyncio.gather(*calls)

    started = time.monotonic()
    outs = asyncio.run(many())
    elapsed = time.monotonic() - started
    echoes = [json.loads(o[0].text).get("echo") for o in outs]
    assert echoes == [f"q{i}" for i in range(20)]
    # Calls overlap instead of serialising (20 x 50 ms would be 1 s).
    assert elapsed < 0.8
