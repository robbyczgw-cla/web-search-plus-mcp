import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server


def test_parallel_search_normalizes_excerpts_and_metadata(monkeypatch):
    captured = {}

    def fake_request(api_url, headers, body, timeout=30):
        captured.update({"api_url": api_url, "headers": headers, "body": body, "timeout": timeout})
        return {
            "search_id": "search-1",
            "session_id": "session-1",
            "results": [
                {
                    "title": "Parallel Docs",
                    "url": "https://docs.parallel.ai/search",
                    "excerpts": [{"text": "First excerpt"}, {"content": "Second excerpt"}],
                }
            ],
        }

    monkeypatch.setattr(search, "make_request", fake_request)
    result = search.search_parallel(
        "parallel api",
        "parallel-test-key",
        max_results=1,
        include_domains=["docs.parallel.ai"],
        exclude_domains=["reddit.com"],
        client_model="claude-sonnet-4",
    )

    assert captured["api_url"] == "https://api.parallel.ai/v1/search"
    assert captured["headers"]["x-api-key"] == "parallel-test-key"
    assert captured["body"] == {
        "objective": "parallel api",
        "search_queries": ["parallel api site:docs.parallel.ai -site:reddit.com"],
        "client_model": "claude-sonnet-4",
    }
    assert captured["timeout"] == 45
    assert result["provider"] == "parallel"
    assert result["results"][0]["snippet"] == "First excerpt\n\nSecond excerpt"
    assert result["metadata"]["search_id"] == "search-1"


def test_parallel_extract_normalizes_full_content_and_errors(monkeypatch):
    captured = {}

    def fake_request(api_url, headers, body, timeout=30):
        captured.update({"api_url": api_url, "headers": headers, "body": body, "timeout": timeout})
        return {
            "search_id": "extract-1",
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Example",
                    "full_content": "Full markdown",
                    "excerpts": [{"text": "Excerpt"}],
                    "extra": "kept",
                }
            ],
            "errors": [{"url": "https://bad.example", "error": "blocked"}],
        }

    monkeypatch.setattr(search, "make_request", fake_request)
    result = search.extract_parallel(["https://example.com"], "parallel-test-key", client_model="gpt-5")

    assert captured["api_url"] == "https://api.parallel.ai/v1/extract"
    assert captured["headers"]["x-api-key"] == "parallel-test-key"
    assert captured["body"]["urls"] == ["https://example.com"]
    assert captured["body"]["max_chars_total"] == 120000
    assert captured["body"]["advanced_settings"]["full_content"] == {"max_chars_per_result": 60000}
    assert captured["body"]["client_model"] == "gpt-5"
    assert captured["timeout"] == 60
    assert result["provider"] == "parallel"
    assert result["results"][0]["content"] == "Full markdown"
    assert result["results"][0]["metadata"] == {"extra": "kept"}
    assert result["results"][1]["error"]


def test_parallel_is_explicit_only_by_default(monkeypatch):
    monkeypatch.setenv("PARALLEL_API_KEY", "parallel-test-key")
    for env in [
        "SERPER_API_KEY", "BRAVE_API_KEY", "TAVILY_API_KEY", "LINKUP_API_KEY", "EXA_API_KEY",
        "FIRECRAWL_API_KEY", "PERPLEXITY_API_KEY", "KILOCODE_API_KEY", "YOU_API_KEY",
        "SEARXNG_INSTANCE_URL", "SERPBASE_API_KEY", "QUERIT_API_KEY",
    ]:
        monkeypatch.delenv(env, raising=False)

    config = search._deepcopy_default_config()
    routing = search.auto_route_provider("parallel api docs", config)

    assert routing["reason"] == "no_available_providers"
    assert config["auto_routing"]["auto_allow"]["parallel"] is False
    assert search.explain_routing("parallel api docs", config)["available_providers"] == []


def test_server_parallel_metadata_and_default_provider_append():
    assert server.SEARCH_PROVIDERS["parallel"] == {
        "env": "PARALLEL_API_KEY",
        "capabilities": ["search", "extract", "citations"],
        "auto_allow": False,
    }
    assert server.EXTRACT_PROVIDERS == ["tavily", "exa", "linkup", "parallel", "firecrawl", "you", "keenable", "serper"]
    assert server._default_behavior_config()["auto_routing"]["auto_allow"]["parallel"] is False

    config = server._normalize_behavior_config({"auto_routing": {"provider_priority": ["tavily", "linkup"]}})
    assert config["auto_routing"]["provider_priority"][:2] == ["tavily", "linkup"]
    assert set(config["auto_routing"]["provider_priority"]) == set(server.ROUTING_PROVIDER_ORDER)
