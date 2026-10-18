"""Merged v3 extraction retains failed/refused slots as well as paid content."""
import pytest

from test_extract_projection_golden import _Engine, _execute
from web_search_plus_mcp.compat_v3 import v3_response_to_legacy_extract


@pytest.mark.parametrize("missing", ["https://example.org/c", "http://127.0.0.1/admin"])
def test_merged_v3_extract_keeps_providerless_error_slot(missing):
    urls = ["https://example.org/a", "https://example.org/b", missing]
    case = {
        "tavily": [{"url": urls[0], "content": "page a"}],
        "linkup": [{"url": urls[1], "content": "page b"}],
    }
    with _Engine(case):
        execution = _execute(urls)
    response = execution.response
    assert len(response.results) == len(urls)
    assert [r["url"]["observed"] for r in response.results] == urls
    assert [(r.get("text") or {}).get("text") for r in response.results] == ["page a", "page b", None]
    attempts = {a.attempt_id: a.provider for a in response.provider_attempts}
    observations = {o["observation_id"]: o for o in response.observations}
    owners = [attempts[observations[r["representative_observation_id"]]["provider_attempt_id"]] for r in response.results]
    assert owners == ["tavily", "linkup", "linkup"]
    legacy = v3_response_to_legacy_extract(execution)
    assert [r["url"] for r in legacy["results"]] == urls
    assert legacy["results"][2]["error"]
