"""Compact MCP output; full snapshots were projected by v5.1.2 (7a8bd57).

The search fixture uses the real runtime's observation/result builder, with
8 ordinary 270-character snippets. 6 KB leaves room for these sources and
routing hints without allowing duplicated evidence back into the response.
"""

from copy import deepcopy
import asyncio
import json
from pathlib import Path

from mcp.types import CallToolRequestParams
import pytest

from web_search_plus_mcp import server

CASES = json.loads((Path(__file__).parent / "fixtures/mcp_detail_512.json").read_text())


def project(case, detail):
    return server._project_v3_payload(
        deepcopy(case["canonical"]),
        **case["options"],
        detail=detail,
        requested_provider="auto",
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_full_is_byte_for_byte_512_projection(case):
    assert json.dumps(project(case, "full"), ensure_ascii=False) == case["full_json"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_modes_preserve_source_text_and_order(case):
    full, compact = project(case, "full"), project(case, "compact")
    assert len(compact["results"]) == len(full["results"])
    fields = (
        ("url", "requested_url", "content", "error")
        if case["options"]["capability"] == "extract"
        else ("title", "url", "snippet")
    )
    assert [[row.get(key) for key in fields] for row in compact["results"]] == [
        [row.get(key) for key in fields] for row in full["results"]
    ]
    assert compact["detail"] == "compact"
    assert 'detail="full"' in compact["hint"]
    assert (
        not {
            "contract_version",
            "observations",
            "provider_attempts",
            "routing_receipt",
            "policy_actions",
            "dedup_clusters",
            "source_diversity",
        }
        & compact.keys()
    )


def test_eight_search_results_fit_token_budget():
    case = CASES[0]
    compact = json.dumps(project(case, "compact"), ensure_ascii=False).encode()
    assert len(project(case, "compact")["results"]) == 8
    assert len(compact) <= len(case["full_json"].encode()) * 0.30
    assert len(compact) <= 6000


@pytest.mark.parametrize("location", ["warnings", "metadata"])
def test_source_quality_counts_fit_compact_budget_and_survive_full(location):
    case = deepcopy(CASES[0])
    counts = {
        "redirects_wrapped": 7, "redirects_resolved": 2,
        "redirects_dropped": 5, "invalid_urls_dropped": 3,
    }
    warnings = [
        {"code": "wsp.search.redirects", "message": "Google source redirects were resolved or dropped.",
         "details": {key: value for key, value in counts.items() if key.startswith("redirects_")}},
        {"code": "wsp.search.invalid_urls", "message": "Corrupt source URLs were dropped.",
         "details": {"invalid_urls_dropped": 3}},
    ]
    case["canonical"][location] = warnings if location == "warnings" else counts
    compact, full = project(case, "compact"), project(case, "full")
    assert {key: compact[key] for key in counts} == counts
    assert full[location] == case["canonical"][location]
    assert compact["results"] == project(CASES[0], "compact")["results"]
    size = len(json.dumps(compact, ensure_ascii=False).encode())
    assert size <= len(json.dumps(full, ensure_ascii=False).encode()) * 0.30
    assert size < 6000


def test_zero_source_quality_counts_are_omitted_only_from_compact():
    case = deepcopy(CASES[0])
    counts = {"redirects_wrapped": 1, "redirects_resolved": 1, "redirects_dropped": 0,
              "invalid_urls_dropped": 0}
    case["canonical"]["warnings"] = [{
        "code": "wsp.search.redirects", "message": "Google source redirects were resolved or dropped.",
        "details": counts,
    }]
    compact = project(case, "compact")
    assert compact["redirects_wrapped"] == compact["redirects_resolved"] == 1
    assert "redirects_dropped" not in compact
    assert "invalid_urls_dropped" not in compact
    assert project(case, "full")["warnings"][0]["details"] == counts


def test_compact_search_shape_dates_and_small_enrichment():
    payload = project(CASES[0], "compact")
    assert payload["provider"] == "linkup"
    assert payload["query"] == "Football Manager 27 skins modding"
    assert payload["results"][0]["published"] == "2026-10-30"
    assert "published" not in payload["results"][1]
    assert payload["results"][0]["source_type"] == "other"
    assert isinstance(payload["results"][0]["fetch_priority"], str)
    assert "snippet_aggregate" not in payload["results"][0]
    # No fallback happened: no misleading "reason": "none" in the compact summary.
    assert payload["routing"] == {"auto_routed": True}
    assert payload["cached"] is False


def test_fallback_summary_excludes_cancelled_and_later_attempts():
    case = deepcopy(CASES[0])
    case["canonical"]["provider_attempts"] = [
        {"provider": "brave", "outcome": "failed"},
        {"provider": "serper", "outcome": "success", "result_count": 0},
        {"provider": "exa", "outcome": "cancelled"},
        {"provider": "linkup", "outcome": "success", "result_count": 8},
        {"provider": "you", "outcome": "failed"},
    ]
    assert project(case, "compact")["routing"]["fallback_from"] == ["brave", "serper"]


def test_compact_cache_origin_and_age():
    case = deepcopy(CASES[0])
    case["canonical"]["routing_receipt"] = {
        "selected_provider": None,
        "cache_origin": {"selected_provider": "brave"},
    }
    case["canonical"]["provider_attempts"] = []
    case["canonical"]["cache_status"] = {"disposition": "fresh_hit", "age_seconds": 42}
    payload = project(case, "compact")
    assert payload["provider"] == "brave"
    assert payload["cached"] is True
    assert payload["cache_age_seconds"] == 42


def test_compact_research_counts():
    payload = project(CASES[2], "compact")
    assert payload["provider"] == "research"
    assert payload["research"] == {
        "providers_merged": ["linkup", "serper"],
        "pages_count": 2,
    }


def test_compact_extract_preserves_bounds_titles_and_storage_reference():
    payload = project(CASES[1], "compact")
    first, omitted = payload["results"]
    assert first["title"] == "Example Domain"
    assert first["requested_url"] == "https://example.com"
    assert first["url"] == "https://example.com/"
    assert first["content"] == "Bounded page text."
    assert first["full_text"]["truncated"] is True
    assert first["full_text"]["stored"] is True
    assert first["full_text"]["reference"]["key"] == "a" * 64
    assert first["full_text"]["chars"] == 120000
    assert omitted["error"] == "not tried: limit of 1 URLs per call reached"
    assert payload["warnings"] == ["Inline content was truncated."]
    assert "Full unbounded text." not in json.dumps(payload)


def test_compact_extract_reports_failed_storage_and_keeps_spans():
    case = deepcopy(CASES[1])
    case["canonical"]["stored_content"][0] = {
        "observation_id": "obs_page",
        "storage_succeeded": False,
    }
    case["canonical"]["results"][0].update(
        {
            "spans": [{"text": "Bounded", "start": 0, "end": 7}],
            "span_contract_version": "1",
        }
    )
    row = project(case, "compact")["results"][0]
    assert row["full_text"] == {"truncated": True, "stored": False}
    assert row["spans"] == project(case, "full")["results"][0]["spans"]
    assert row["span_contract_version"] == "1"


@pytest.mark.parametrize("detail", ["compact", "full"])
def test_failure_guidance_and_mcp_is_error(monkeypatch, detail):
    case = CASES[3]

    async def fake_run(*args, **kwargs):
        return deepcopy(case["canonical"])

    monkeypatch.setattr(server, "_run_subprocess", fake_run)
    result = asyncio.run(
        server._mcp_call_tool(
            None,
            CallToolRequestParams(
                name="web_search",
                arguments={"query": "q", "detail": detail},
            ),
        )
    )
    payload = json.loads(result.content[0].text)
    assert result.is_error is True
    assert len(result.content) == 1
    assert payload["status"] == "failed"
    assert "LINKUP_API_KEY" in result.content[0].text
    assert "web-search-plus-mcp setup linkup" in result.content[0].text
    if detail == "compact":
        assert payload["env_var"] == "LINKUP_API_KEY"
        assert payload["provider_errors"] == ["linkup: missing_credentials"]
        assert "error_v3" not in payload


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("web_search", {"query": "q"}),
        ("web_extract", {"urls": ["https://example.com"]}),
    ],
)
@pytest.mark.parametrize(
    "argument,env,config,expected",
    [
        (None, None, None, "compact"),
        (None, None, "full", "full"),
        (None, "compact", "full", "compact"),
        (None, "full", "compact", "full"),
        ("compact", "full", "full", "compact"),
        ("full", "compact", "compact", "full"),
    ],
)
def test_detail_precedence_at_tool_boundary(
    monkeypatch, tmp_path, tool, arguments, argument, env, config, expected
):
    path = tmp_path / "config.json"
    if config:
        server._write_behavior_config({"mcp": {"detail": config}}, path)
    monkeypatch.setenv(server.CONFIG_ENV_VAR, str(path))
    monkeypatch.delenv(server.DETAIL_ENV_VAR, raising=False)
    if env:
        monkeypatch.setenv(server.DETAIL_ENV_VAR, env)
    arguments = dict(arguments)
    if argument:
        arguments["detail"] = argument

    async def fake_run(*args, **kwargs):
        return deepcopy(CASES[0]["canonical"])

    monkeypatch.setattr(server, "_run_subprocess", fake_run)
    payload = json.loads(asyncio.run(server.call_tool(tool, arguments))[0].text)
    assert ("contract_version" in payload) == (expected == "full")
    assert payload.get("detail") == ("compact" if expected == "compact" else None)


@pytest.mark.parametrize("detail", ["compact", "full"])
def test_unexpected_failure_uses_requested_shape(monkeypatch, detail):
    async def explode(*args, **kwargs):
        raise RuntimeError("private detail")

    monkeypatch.setattr(server, "call_tool", explode)
    result = asyncio.run(
        server._mcp_call_tool(
            None,
            CallToolRequestParams(
                name="web_search",
                arguments={"query": "q", "detail": detail},
            ),
        )
    )
    payload = json.loads(result.content[0].text)
    assert result.is_error is True
    assert payload["status"] == "failed"
    assert ("contract_version" in payload) == (detail == "full")
    assert "private detail" not in result.content[0].text


def test_detail_schema_rejects_unknown_value_before_execution(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("invalid detail must not dispatch")

    monkeypatch.setattr(server, "call_tool", forbidden)
    with pytest.raises(server.MCPError, match="validation failed at detail"):
        asyncio.run(
            server._mcp_call_tool(
                None,
                CallToolRequestParams(
                    name="web_search",
                    arguments={"query": "q", "detail": "verbose"},
                ),
            )
        )


def test_config_commands_preserve_detail_default(tmp_path, capsys):
    path = tmp_path / "config.json"
    server._write_behavior_config({"mcp": {"detail": "full"}}, path)
    assert (
        server.cli_main(["config", "--config-path", str(path), "set-routing", "off"])
        == 0
    )
    capsys.readouterr()
    assert server._load_behavior_config(path)[0]["mcp"]["detail"] == "full"


def test_research_does_not_report_unknown_page_count_as_zero():
    case = deepcopy(CASES[2])
    case["canonical"]["provider_attempts"] = [
        attempt
        for attempt in case["canonical"]["provider_attempts"]
        if attempt.get("capability") != "extract"
    ]
    assert "pages_count" not in project(case, "compact")["research"]


def test_warning_and_failure_reasons_do_not_repeat_nested_details():
    case = deepcopy(CASES[3])
    case["canonical"]["warnings"] = [
        {"message": "Warning " * 100, "details": {"private_internal": "x" * 5000}}
    ]
    case["canonical"]["provider_attempts"] = [
        {
            "provider": "serper",
            "outcome": "failed",
            "error": {"message": "Failure " * 100, "details": {"internal": "x" * 5000}},
        },
        {"provider": "brave", "outcome": "success", "result_count": 0},
    ]
    payload = project(case, "compact")
    assert len(payload["warnings"][0]) <= 240
    assert len(payload["provider_errors"][0]) <= 248
    assert payload["provider_errors"][1] == "brave: empty results"
    assert "private_internal" not in json.dumps(payload)


@pytest.mark.inprocess
@pytest.mark.parametrize(
    "tool,case_index,arguments",
    [
        ("web_search", 0, {"query": "q", "count": 8}),
        ("web_extract", 1, {"urls": ["https://example.com"]}),
    ],
)
def test_detail_changes_only_output_at_inprocess_boundary(
    monkeypatch, tool, case_index, arguments
):
    from web_search_plus_mcp import search

    calls = []

    def fake(argv, *, config=None):
        calls.append(argv)
        return deepcopy(CASES[case_index]["canonical"]), 0

    monkeypatch.setattr(search, "run_cli_contract_v3", fake)
    full = json.loads(
        asyncio.run(server.call_tool(tool, {**arguments, "detail": "full"}))[0].text
    )
    compact = json.loads(
        asyncio.run(server.call_tool(tool, {**arguments, "detail": "compact"}))[0].text
    )
    assert calls[0] == calls[1]
    fields = (
        ("url", "content") if tool == "web_extract" else ("title", "url", "snippet")
    )
    assert [[row.get(field) for field in fields] for row in compact["results"]] == [
        [row.get(field) for field in fields] for row in full["results"]
    ]
