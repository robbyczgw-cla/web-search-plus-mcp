import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    tomllib = importlib.import_module("tomli")

import web_search_plus_mcp
import web_search_plus_mcp.server as server


ROOT = Path(__file__).resolve().parents[1]
RETIRED_ANSWER_PROVIDERS = {"perplexity", "kilo-perplexity"}


def run(coro):
    return asyncio.run(coro)


def tool(name):
    return next(item for item in run(server.list_tools()) if item.name == name)


def canonical_response(*, capability="search", status="ok", results=None, error=None):
    return {
        "contract_version": "3.0",
        "request_id": "req_test",
        "execution_id": "exec_test",
        "capability": capability,
        "status": status,
        "results": results or [],
        "observations": [],
        "policy_actions": [],
        "source_diversity": {
            "method": "provider_host_family_clusters",
            "method_version": "1",
            "method_degraded": False,
            "provider_count": 1,
            "host_count": 1,
            "source_family_count": 1,
            "unique_cluster_count": 1,
        },
        "provider_attempts": [
            {
                "attempt_id": "attempt-1",
                "provider": "linkup",
                "capability": capability,
                "outcome": "success",
                "retry_count": 0,
                "result_count": len(results or []),
            }
        ],
        "routing_receipt": {
            "selected_provider": "linkup",
            "candidate_order": ["linkup"],
        },
        "cache_status": {"disposition": "miss"},
        "limits_applied": {},
        "stored_content": [],
        "dedup_clusters": [],
        "warnings": [],
        "error": error,
    }


def test_version_1_1_1_is_consistent_across_public_surfaces():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["project"]["version"] == "1.1.1"
    assert project["project"]["scripts"]["web-search-plus-mcp"] == (
        "web_search_plus_mcp.server:cli_main"
    )
    assert web_search_plus_mcp.__version__ == "1.1.1"
    assert server.__version__ == "1.1.1"
    initialization = server.app.create_initialization_options()
    assert initialization.server_name == "web-search-plus"
    assert initialization.server_version == "1.1.1"


def test_wheel_config_includes_v3_contracts_and_migration_guide():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    forced = project["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert forced["schemas"] == "web_search_plus_mcp/schemas"
    assert forced["docs/MIGRATION_1_0.md"] == (
        "web_search_plus_mcp/docs/MIGRATION_1_0.md"
    )


def test_source_only_provider_surface_is_12_search_and_8_extract():
    assert len(server.SEARCH_PROVIDERS) == 12
    assert len(server.EXTRACT_PROVIDERS) == 8
    assert RETIRED_ANSWER_PROVIDERS.isdisjoint(server.SEARCH_PROVIDERS)
    assert RETIRED_ANSWER_PROVIDERS.isdisjoint(server.EXTRACT_PROVIDERS)

    search_enum = tool("web_search").inputSchema["properties"]["provider"]["enum"]
    extract_enum = tool("web_extract").inputSchema["properties"]["provider"]["enum"]
    assert search_enum == ["auto", *server.SEARCH_PROVIDERS]
    assert extract_enum == ["auto", *server.EXTRACT_PROVIDERS]


def test_readme_describes_current_source_only_release_surface():
    readme = (ROOT / "README.md").read_text()
    assert "`1.1.1`" in readme
    assert "Web Search Plus v3.1.1" in readme
    assert "**12 search providers" in readme

    provider_section = readme.split("## 🔎 Search Providers", 1)[1].split(
        "## 📄 Extract Providers", 1
    )[0]
    search_tool_section = readme.split("### `web_search`", 1)[1].split(
        "### `web_extract`", 1
    )[0]
    for provider in RETIRED_ANSWER_PROVIDERS:
        display_name = "Kilo Perplexity" if provider == "kilo-perplexity" else "Perplexity"
        assert f"- **{display_name}**" not in provider_section
        assert f"`{provider}`" not in search_tool_section


def test_glama_manifest_matches_live_tool_schemas():
    manifest = json.loads((ROOT / "glama.json").read_text())
    expected = [
        item.model_dump(by_alias=True, exclude_none=True)
        for item in run(server.list_tools())
    ]
    assert manifest["tools"] == expected

    by_name = {tool["name"]: tool for tool in expected}
    assert manifest["features"]["providers"] == by_name["web_search"][
        "inputSchema"
    ]["properties"]["provider"]["enum"][1:]
    assert manifest["features"]["extractProviders"] == by_name["web_extract"][
        "inputSchema"
    ]["properties"]["provider"]["enum"][1:]


def test_tool_surface_stays_two_tools_and_describes_source_only_contract():
    tools = run(server.list_tools())
    assert [item.name for item in tools] == ["web_search", "web_extract"]
    descriptions = " ".join(item.description.lower() for item in tools)
    assert "source-only" in descriptions
    assert "synthesized answer" not in descriptions
    assert "14 search" not in descriptions


def test_retired_answer_provider_returns_typed_error_without_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("retired answer providers must fail before subprocess dispatch")

    monkeypatch.setattr(server.subprocess, "run", forbidden)
    content = run(server.call_tool("web_search", {
        "query": "answer this",
        "provider": "perplexity",
    }))
    payload = json.loads(content[0].text)
    assert payload["results"] == []
    assert payload["provider"] == "perplexity"
    assert payload["error_v3"] == {
        "error_class": "unsupported",
        "code": "wsp.provider.source_only_required",
        "message": "Provider 'perplexity' is unavailable because Web Search Plus 3.0 is source-only.",
        "retryable": False,
        "provider": "perplexity",
    }
    assert isinstance(payload["error"], str)
    assert "answer" not in payload


def test_search_projects_canonical_v3_to_additive_legacy_shape(monkeypatch):
    canonical = canonical_response(results=[{
        "representative_observation_id": "obs_1",
        "observation_ids": ["obs_1"],
        "url": {"observed": "https://example.com/a", "canonical": "https://example.com/a"},
        "title": {"text": "Example title"},
        "snippet": {"text": "Provider-grounded snippet"},
        "text": None,
    }])
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps(canonical), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "example query",
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert "--contract-v3" in seen["cmd"]
    assert payload["provider"] == "linkup"
    assert payload["query"] == "example query"
    assert payload["results"] == [{
        "title": "Example title",
        "url": "https://example.com/a",
        "snippet": "Provider-grounded snippet",
    }]
    assert payload["contract_version"] == "3.0"
    assert payload["status"] == "ok"
    assert payload["provider_attempts"] == canonical["provider_attempts"]
    assert payload["routing_receipt"] == canonical["routing_receipt"]
    assert "answer" not in json.dumps(payload).lower()


def test_research_projection_preserves_aggregate_identity_and_v3_evidence(monkeypatch):
    canonical = canonical_response(results=[{
        "representative_observation_id": "obs_linkup",
        "observation_ids": ["obs_linkup", "obs_serper"],
        "url": {"observed": "https://example.com/research", "canonical": "https://example.com/research"},
        "title": {"text": "Merged research result"},
        "snippet": {"text": "Evidence merged across providers"},
        "text": None,
    }])
    canonical["provider_attempts"] = [
        {
            "attempt_id": "attempt-linkup",
            "provider": "linkup",
            "capability": "search",
            "outcome": "success",
            "retry_count": 0,
            "result_count": 1,
        },
        {
            "attempt_id": "attempt-serper",
            "provider": "serper",
            "capability": "search",
            "outcome": "success",
            "retry_count": 0,
            "result_count": 1,
        },
    ]
    canonical["observations"] = [
        {"observation_id": "obs_linkup", "provider": "linkup", "provider_attempt_id": "attempt-linkup"},
        {"observation_id": "obs_serper", "provider": "serper", "provider_attempt_id": "attempt-serper"},
    ]
    canonical["routing_receipt"] = {
        "mode": "classic",
        "selected_provider": "linkup",
        "candidate_order": ["linkup", "serper"],
    }
    seen = {}

    def fake_run(cmd, capture_output, text, env, timeout):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps(canonical), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "compare alpha beta",
        "provider": "auto",
        "mode": "research",
        "research_time_budget": 12.0,
    }))
    payload = json.loads(content[0].text)

    assert seen["cmd"][seen["cmd"].index("--mode") + 1] == "research"
    assert payload["provider"] == "research"
    assert payload["provider_attempts"] == canonical["provider_attempts"]
    assert payload["observations"] == canonical["observations"]
    assert payload["results"][0]["snippet"] == "Evidence merged across providers"


def test_extract_cache_hit_projection_preserves_body_and_cache_provenance(monkeypatch):
    canonical = canonical_response(
        capability="extract",
        results=[{
            "representative_observation_id": "obs_cached",
            "observation_ids": ["obs_cached"],
            "url": {"observed": "https://example.com/cached", "canonical": "https://example.com/cached"},
            "title": None,
            "snippet": None,
            "text": {"text": "cached full body"},
        }],
    )
    canonical["cache_status"] = {
        "disposition": "fresh_hit",
        "origin_execution_id": "exec_origin",
    }
    canonical["provider_attempts"] = []

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=0, stdout=json.dumps(canonical), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_extract", {
        "urls": ["https://example.com/cached"],
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert payload["results"] == [{
        "url": "https://example.com/cached",
        "content": "cached full body",
    }]
    assert payload["cache_status"] == canonical["cache_status"]
    assert payload["provider_attempts"] == []


def test_extract_projection_preserves_bounds_and_page_on_demand_reference(monkeypatch):
    stored = {
        "observation_id": "obs_1",
        "storage_attempted": True,
        "storage_succeeded": True,
        "reference": {
            "store": "web_text_v3",
            "key": "a" * 64,
            "media_type": "text/markdown",
        },
        "full_text_sha256": "b" * 64,
        "full_text_chars": 120000,
    }
    canonical = canonical_response(
        capability="extract",
        status="degraded",
        results=[{
            "representative_observation_id": "obs_1",
            "observation_ids": ["obs_1"],
            "url": {"observed": "https://example.com/a", "canonical": "https://example.com/a"},
            "title": None,
            "snippet": None,
            "text": {"text": "bounded inline text"},
        }],
    )
    canonical["limits_applied"] = {"extract": {
        "requested_url_count": 1,
        "processed_urls": ["https://example.com/a"],
        "omitted_urls": [],
        "omitted_url_count": 0,
        "max_urls": 10,
        "max_context_chars": 60000,
        "context_chars_returned": 19,
        "truncated": True,
    }}
    canonical["stored_content"] = [stored]
    canonical["warnings"] = [{
        "code": "wsp.content.truncated",
        "message": "Inline extracted content was deterministically truncated to the call budget.",
        "details": {"truncated_result_count": 1},
    }]

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=0, stdout=json.dumps(canonical), stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_extract", {
        "urls": ["https://example.com/a"],
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert payload["results"] == [{
        "url": "https://example.com/a",
        "content": "bounded inline text",
    }]
    assert payload["status"] == "degraded"
    assert payload["limits_applied"]["extract"]["truncated"] is True
    assert payload["stored_content"] == [stored]
    assert payload["warnings"][0]["code"] == "wsp.content.truncated"


def test_subprocess_nonzero_canonical_error_remains_typed(monkeypatch):
    error = {
        "error_class": "config",
        "code": "wsp.config.missing_credentials",
        "message": "No configured source provider is available.",
        "retryable": False,
        "provider": "linkup",
    }
    canonical = canonical_response(status="failed", error=error)

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(returncode=1, stdout="", stderr=json.dumps(canonical))

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "example",
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert payload["results"] == []
    assert payload["error"] == error["message"]
    assert payload["error_v3"] == error
    assert payload["status"] == "failed"


def test_subprocess_non_json_failure_is_typed_legacy_compatible_and_secret_free(
    monkeypatch,
):
    secret = "super-secret-subprocess-token"

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=f"Authorization: Bearer {secret}",
        )

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "example",
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert payload["error"] == "Web Search Plus subprocess failed."
    assert payload["error_v3"]["code"] == "wsp.subprocess.failed"
    assert payload["error_v3"]["message"] == payload["error"]
    assert secret not in json.dumps(payload)


def test_subprocess_non_json_success_is_typed_and_secret_free(monkeypatch):
    secret = "super-secret-stdout-token"

    def fake_run(cmd, capture_output, text, env, timeout):
        return SimpleNamespace(
            returncode=0,
            stdout=f"unexpected output containing {secret}",
            stderr="",
        )

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "example",
        "provider": "linkup",
    }))
    payload = json.loads(content[0].text)

    assert payload["error"] == "Web Search Plus subprocess returned an invalid response."
    assert payload["error_v3"]["code"] == "wsp.subprocess.invalid_response"
    assert payload["error_v3"]["message"] == payload["error"]
    assert secret not in json.dumps(payload)


def test_subprocess_timeout_is_typed_retryable_and_secret_free(monkeypatch):
    secret = "super-secret-timeout-output"

    def fake_run(cmd, capture_output, text, env, timeout):
        raise server.subprocess.TimeoutExpired(
            cmd=[*cmd, secret],
            timeout=timeout,
            output=secret,
            stderr=secret,
        )

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    content = run(server.call_tool("web_search", {
        "query": "maximum budget",
        "mode": "research",
        "research_time_budget": 75,
    }))
    payload = json.loads(content[0].text)

    assert payload["status"] == "failed"
    assert payload["results"] == []
    assert payload["error"] == "Web Search Plus subprocess timed out."
    assert payload["error_v3"] == {
        "error_class": "timeout",
        "code": "wsp.subprocess.timeout",
        "message": payload["error"],
        "retryable": True,
        "provider": None,
    }
    assert secret not in json.dumps(payload)
