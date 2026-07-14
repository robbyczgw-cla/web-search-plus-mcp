from pathlib import Path

import web_search_plus_mcp.cache as cache
from web_search_plus_mcp.bounded_context_v3 import FullTextStore, apply_bounded_context, prepare_extract_request
from web_search_plus_mcp.contract_v3 import Capability, RequestV3, ResponseStatus, ResponseV3
from web_search_plus_mcp.runtime_v3 import observations_from_legacy, project_results_from_observations


def test_store_web_text_caps_and_writes_under_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    text = "x" * 25

    metadata = cache.store_web_text("https://example.com/a", text, max_chars=10)

    assert metadata["stored"] is True
    assert metadata["capped"] is True
    assert metadata["original_chars"] == 25
    stored_path = Path(metadata["path"])
    assert stored_path.exists()
    stored = stored_path.read_text()
    assert stored.startswith("x" * 10)
    assert "TRUNCATED" in stored


def test_v3_bounded_context_truncates_and_stores_full_text_truthfully(tmp_path):
    full_text = "A" * 2500
    raw = [{"url": "https://example.com/large", "title": "Large", "content": full_text}]
    observations = observations_from_legacy(
        {"results": raw}, "tavily", Capability.EXTRACT, "attempt_test"
    )
    response = ResponseV3(
        request_id="req_test",
        execution_id="exec_test",
        capability=Capability.EXTRACT,
        status=ResponseStatus.OK,
        results=project_results_from_observations(observations, raw),
        observations=observations,
        policy_actions=[],
        provider_attempts=[],
        routing_receipt={
            "policy_id": "classic",
            "policy_revision": "test",
            "mode": "classic",
            "candidate_order": ["tavily"],
            "selected_provider": "tavily",
            "fallback_reason": "none",
        },
        cache_status={"disposition": "miss"},
    )
    request = RequestV3.extract(["https://example.com/large"], max_context_chars=1000)
    plan = prepare_extract_request(request, {})
    bounded = apply_bounded_context(
        response,
        request,
        plan,
        store=FullTextStore(tmp_path),
    ).to_dict()

    assert bounded["limits_applied"]["extract"]["truncated"] is True
    assert bounded["limits_applied"]["extract"]["max_context_chars"] == 1000
    assert len(bounded["results"][0]["text"]["text"]) <= 1000
    assert bounded["stored_content"][0]["storage_succeeded"] is True
    assert bounded["stored_content"][0]["reference"]["store"] == "web_text_v3"
