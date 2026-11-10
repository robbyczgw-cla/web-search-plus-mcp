"""Research evidence at the real MCP stdio boundary; only HTTP is replaced."""

import json
import os
from pathlib import Path
import subprocess
import select
import sys

import jsonschema
import pytest

from web_search_plus_mcp.config import _deepcopy_default_config

SENTINEL = "EXTRACTED_PAGE_SENTINEL_7f31"
ROOT = Path(__file__).resolve().parents[1]

# Runs the actual server and adapters, including response normalization, content
# limits, storage, cache and the MCP tools/call handler. Never reaches a provider.
BOOTSTRAP = r'''
import io
import json
import os
from urllib.parse import urlsplit
from web_search_plus_mcp import http_client

def fixture_http(req, timeout=30):
    assert urlsplit(req.full_url).hostname == "api.tavily.com", req.full_url
    body = json.loads(req.data)
    with open(os.environ["HTTP_TRACE"], "a") as trace:
        trace.write(urlsplit(req.full_url).path + "\n")
    if req.full_url.endswith("/search"):
        data = {"results": [
            {"url": f"https://93.184.216.34/{i}", "title": f"Source {i}",
             "content": "Ordinary search snippet. " * 11}
            for i in range(body["max_results"])
        ]}
    else:
        assert req.full_url.endswith("/extract")
        scenario = os.environ["EVIDENCE_SCENARIO"]
        urls = body["urls"]
        good = urls if scenario == "success" else urls[:1] if scenario == "partial" else []
        data = {
            "results": [{"url": url, "raw_content":
                "EXTRACTED_PAGE_SENTINEL_7f31 " + "page evidence café. " * 2000}
                for url in good],
            "failed_results": [{"url": url, "error": "HTTP 404 page not found"}
                for url in urls if url not in good],
        }
    return io.BytesIO(json.dumps(data).encode())

http_client.urlopen = fixture_http
from web_search_plus_mcp.server import cli_main
cli_main()
'''


def stdio_research(tmp_path, scenario, context_chars=1000):
    config = _deepcopy_default_config()
    config["auto_routing"].update({"provider_priority": ["tavily"],
                                   "extract_provider_priority": ["tavily"],
                                   "auto_allow": {"tavily": True}})
    config["quality"].update({"filter_spam": False, "max_results_per_domain": 0})
    config["bounded_context"].update({"max_context_chars": context_chars,
                                      "cache_root": str(tmp_path / "text")})
    config["v3"] = {"state_path": str(tmp_path / "state.sqlite3"),
                    "cache_dir": str(tmp_path / "cache")}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path),
           # This checkout, not whatever web_search_plus_mcp the interpreter has installed.
           "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
           "WEB_SEARCH_PLUS_CONFIG": str(config_path), "TAVILY_API_KEY": "fixture-only",
           "WSP_CACHE_DIR": str(tmp_path / "cache"),
           "HTTP_TRACE": str(tmp_path / "http-trace"), "EVIDENCE_SCENARIO": scenario}
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "research-evidence-test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]
    for index, detail in enumerate(("compact", "full"), start=2):
        messages.append({"jsonrpc": "2.0", "id": index, "method": "tools/call",
                         "params": {"name": "web_search", "arguments": {
                             "query": "page evidence café", "provider": "tavily", "mode": "research",
                             "count": 8, "research_time_budget": 10,
                             "detail": detail, "no_cache": True}}})
    proc = subprocess.Popen([sys.executable, "-c", BOOTSTRAP],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env, cwd=tmp_path)
    outputs = []
    try:
        for message in messages:
            proc.stdin.write(json.dumps(message) + "\n")
            proc.stdin.flush()
            if "id" not in message:
                continue
            assert select.select([proc.stdout], [], [], 25)[0], "MCP response timed out"
            response = json.loads(proc.stdout.readline())
            assert "result" in response, response
            if message["id"] == 1:
                continue
            result = response["result"]
            assert not result.get("isError"), result
            text = result["content"][0]["text"]
            outputs.append((json.loads(text), text))
    finally:
        proc.kill()
        proc.wait(10)
        proc.stdin.close()
        proc.stdout.close()
        proc.stderr.close()
    trace = (tmp_path / "http-trace").read_text().splitlines()
    assert trace.count("/search") == 2
    assert trace.count("/extract") == (1 if scenario == "success" else 2)
    return outputs


@pytest.mark.parametrize("scenario", ["success", "partial", "failed"])
def test_research_evidence_and_failures_reach_stdio_client(tmp_path, scenario):
    (compact, compact_text), (full, full_text) = stdio_research(tmp_path, scenario)
    print(f"{scenario}: compact_bytes={len(compact_text.encode())}, full_bytes={len(full_text.encode())}, "
          f"compact_sentinel={SENTINEL in compact_text}, full_sentinel={SENTINEL in full_text}")
    assert len(compact_text.encode()) <= 6000
    if scenario != "failed":
        assert SENTINEL in compact_text
        assert SENTINEL in full_text
    evidence = next(w["details"] for w in full["warnings"] if w["code"] == "wsp.research.evidence")
    assert evidence["pages_count"] == {"success": 3, "partial": 1, "failed": 0}[scenario]
    assert compact["research"]["pages_count"] == evidence["pages_count"]
    assert sum(len(s.get("content", "")) for s in evidence["sources"]) <= 1000
    assert len(full["results"]) == len(compact["results"]) == 8
    schema = json.loads((ROOT / "schemas/v3/response.schema.json").read_text())
    for warning in full["warnings"]:
        jsonschema.validate(warning, {"$ref": "#/$defs/WarningV3", "$defs": schema["$defs"]})
    if scenario != "success":
        assert "404" in compact_text and "404" in full_text
        assert compact["status"] == full["status"] == "degraded"
        assert evidence["failed_count"] == (2 if scenario == "partial" else 3)
    else:
        assert evidence["truncated"] is True
        assert full["status"] == "ok"


def test_large_research_evidence_keeps_compact_small(tmp_path):
    (compact, compact_text), (full, full_text) = stdio_research(tmp_path, "success", 60000)
    print(f"large: compact_bytes={len(compact_text.encode())}, full_bytes={len(full_text.encode())}")
    assert SENTINEL in compact_text and SENTINEL in full_text
    assert len(compact_text.encode()) <= 6000
    assert len(compact_text.encode()) < len(full_text.encode()) * 0.30
    assert compact["research"]["truncated"] is True


@pytest.mark.parametrize("failure", ["returned_error", "empty", "exception", "empty_page", "deadline"])
def test_research_child_failure_reasons_survive_v3_and_compact(failure):
    from web_search_plus_mcp.contract_v3 import (
        AttemptOutcome, Capability, ProviderAttemptV3, RequestV3,
    )
    from web_search_plus_mcp.orchestrator_v3 import ProviderPlan
    from web_search_plus_mcp.research import run_research_mode
    from web_search_plus_mcp.runtime_v3 import response_from_legacy
    from web_search_plus_mcp.server import _project_v3_payload

    url = "https://93.184.216.34/0"

    def extract(_urls):
        if failure == "exception":
            raise RuntimeError("fixture extraction exploded")
        if failure == "returned_error":
            return {"error": "All extraction providers failed", "results": []}
        if failure == "empty_page":
            return {"results": [{"url": url, "content": ""}]}
        return {"results": []}

    clock = [0]

    def search(_provider):
        if failure == "deadline":
            clock[0] = 2
        return {"results": [{"url": url, "title": "Page", "snippet": "search only"}]}

    payload = run_research_mode(
        query="evidence", research_providers=["tavily"], execute_search=search,
        extract_urls=extract, max_results=1,
        time_budget_seconds=1 if failure == "deadline" else None,
        now_fn=lambda: clock[0],
    )
    payload["_v3_raw_results"] = [{**row, "provider": "tavily"} for row in payload["results"]]
    payload["_v3_provider_attempts"] = [ProviderAttemptV3(
        attempt_id="attempt_fixture", provider="tavily", capability=Capability.SEARCH,
        outcome=AttemptOutcome.SUCCESS, result_count=1,
        endpoint_id="tavily:search",
        tries=[{"try_number": 1, "started_at": "2026-11-08T12:00:00Z",
                "duration_ms": 1, "outcome": "success", "error": None}],
    )]
    response = response_from_legacy(
        RequestV3(capability=Capability.SEARCH, input={"query": "evidence"}),
        ProviderPlan(("tavily",), "tavily"), payload,
    ).to_dict()
    schema = json.loads((ROOT / "schemas/v3/response.schema.json").read_text())
    jsonschema.validate(response, schema)
    compact = _project_v3_payload(response, capability="search", request_mode="research", detail="compact")
    assert compact["status"] == response["status"] == "degraded"
    assert compact["research"]["pages_count"] == 0
    expected = {
        "returned_error": "All extraction providers failed", "empty": "no source text",
        "exception": "fixture extraction exploded", "empty_page": "no source text",
        "deadline": "research time budget exhausted",
    }[failure]
    assert expected in json.dumps(response)
    assert expected in json.dumps(compact)
