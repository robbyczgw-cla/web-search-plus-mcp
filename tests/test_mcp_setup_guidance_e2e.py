"""Client-visible missing-key guidance and MCP isError semantics.

These tests exercise the real classification path and the real stdio server,
so a fix that only changes the place where guidance is generated (but not what
the MCP client receives) cannot pass.
"""

import json
import os
import subprocess
import sys

import pytest

from wsp_sdk.errors import ProviderConfigError
from web_search_plus_mcp.config import validate_api_key
from web_search_plus_mcp.errors_v3 import classify_provider_error


def _config_error(provider: str) -> ProviderConfigError:
    with pytest.raises(ProviderConfigError) as caught:
        validate_api_key(provider, {})
    return caught.value


def test_missing_key_guidance_survives_classification(monkeypatch):
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    error = classify_provider_error(_config_error("tinyfish"), provider="tinyfish")
    assert error.code == "wsp.config.provider_invalid"
    assert error.message == "Missing API key for tinyfish"
    assert error.details["env_var"] == "TINYFISH_API_KEY"
    assert error.details["setup_required"] is True
    assert any("web-search-plus-mcp setup" in step for step in error.details["how_to_fix"])
    assert not any("config.json" in step for step in error.details["how_to_fix"])


def test_missing_searxng_url_guidance_survives(monkeypatch):
    monkeypatch.delenv("SEARXNG_INSTANCE_URL", raising=False)
    error = classify_provider_error(_config_error("searxng"), provider="searxng")
    assert error.message == "Missing SearXNG instance URL"
    assert error.details["env_var"] == "SEARXNG_INSTANCE_URL"


@pytest.mark.parametrize(
    "body",
    [
        "upstream said: token sk-live-123 is wrong",
        json.dumps({"error": "SearXNG instance URL must start with http:// or https://", "provided": "ftp://secret.internal"}),
        json.dumps({"error": "Missing API key for tinyfish", "env_var": "x; rm -rf /", "how_to_fix": ["a"]}),
        json.dumps({"error": "Missing API key for tinyfish https://evil.example/?k=1", "env_var": "TINYFISH_API_KEY", "how_to_fix": ["a"]}),
        json.dumps(["not", "a", "dict"]),
    ],
)
def test_untrusted_config_error_text_stays_redacted(body):
    error = classify_provider_error(ProviderConfigError(body), provider="tinyfish")
    assert error.message == "Provider configuration is invalid"
    assert error.details == {}
    assert "secret.internal" not in json.dumps(error.to_dict())
    assert "sk-live" not in json.dumps(error.to_dict())


def _stdio_call(home, calls):
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(home)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "web_search_plus_mcp.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, cwd=str(home),
    )

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"}}})
        assert json.loads(proc.stdout.readline())["id"] == 1
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        out = []
        for index, (name, arguments) in enumerate(calls, start=2):
            send({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                  "params": {"name": name, "arguments": arguments}})
            out.append(json.loads(proc.stdout.readline())["result"])
        return out
    finally:
        proc.kill()
        proc.wait(10)


def test_stdio_client_sees_guidance_and_is_error_without_keys(tmp_path):
    search, explicit, extract = _stdio_call(tmp_path, [
        ("web_search", {"query": "python asyncio taskgroup"}),
        ("web_search", {"query": "python asyncio taskgroup", "provider": "tinyfish"}),
        ("web_extract", {"urls": ["https://example.com"]}),
    ])
    for result in (search, explicit, extract):
        assert result["isError"] is True
        text = result["content"][0]["text"]
        payload = json.loads(text)
        assert payload["status"] == "failed"
        assert "web-search-plus-mcp setup" in text
        assert "config.json" not in text
    explicit_payload = json.loads(explicit["content"][0]["text"])
    assert explicit_payload["error_v3"]["details"]["env_var"] == "TINYFISH_API_KEY"
