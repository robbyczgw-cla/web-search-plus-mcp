import asyncio

import web_search_plus_mcp.search as search
import web_search_plus_mcp.server as server


def test_serpbase_and_querit_are_explicit_only_by_default(monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "serpbase-test-key")
    monkeypatch.setenv("QUERIT_API_KEY", "querit-test-key")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("LINKUP_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("KILOCODE_API_KEY", raising=False)
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_INSTANCE_URL", raising=False)

    config = search._deepcopy_default_config()
    routing = search.auto_route_provider("iphone 16 price today", config)

    assert routing["reason"] == "no_available_providers"
    assert set(routing["auto_allow_excluded"]) == {"serpbase", "querit"}
    assert search.explain_routing("iphone 16 price today", config)["available_providers"] == []


def test_serpbase_can_be_called_explicitly(monkeypatch):
    captured = {}

    def fake_request(api_url, headers, body, timeout=30):
        captured.update({"api_url": api_url, "headers": headers, "body": body, "timeout": timeout})
        return {
            "status": 0,
            "organic": [
                {
                    "title": "Example",
                    "link": "https://example.com/page?utm_source=x&keep=1",
                    "snippet": "Snippet",
                    "rank": 1,
                    "display_link": "example.com",
                }
            ],
            "related_searches": [{"query": "example related"}],
            "answer_box": {"answer": "Answer"},
            "session_id": "sess-1",
        }

    monkeypatch.setattr(search, "make_request", fake_request)
    result = search.search_serpbase(
        query="example",
        api_key="serpbase-test-key",
        max_results=1,
        country="at",
        language="de",
        page=2,
        timeout=12,
    )

    assert captured["api_url"] == "https://api.serpbase.dev/google/search"
    assert captured["headers"]["X-API-Key"] == "serpbase-test-key"
    assert captured["body"] == {"q": "example", "hl": "de", "gl": "at", "page": 2}
    assert captured["timeout"] == 12
    assert result["provider"] == "serpbase"
    assert "answer" not in result
    assert result["results"][0]["url"] == "https://example.com/page?keep=1"
    assert result["related_searches"] == ["example related"]


def test_server_schema_exposes_serpbase_last_and_auto_allow_metadata():
    provider_enum = next(t for t in asyncio.run(server.list_tools()) if t.name == "web_search").inputSchema["properties"]["provider"]["enum"]

    assert provider_enum == [
        "auto",
        "serper",
        "serpbase",
        "brave",
        "tavily",
        "querit",
        "linkup",
        "exa",
        "firecrawl",
        "parallel",
        "you",
        "searxng",
        "keenable",
        "hound",
    ]
    assert server.SEARCH_PROVIDERS["serpbase"]["env"] == "SERPBASE_API_KEY"
    assert server.SEARCH_PROVIDERS["serpbase"]["auto_allow"] is False
    assert server.SEARCH_PROVIDERS["querit"]["auto_allow"] is False
    assert server.ROUTING_PROVIDER_ORDER == [
        "you",
        "serper",
        "exa",
        "firecrawl",
        "tavily",
        "linkup",
        "brave",
        "parallel",
        "serpbase",
        "querit",
        "searxng",
        "keenable",
    ]

    config = server._default_behavior_config()
    assert config["auto_routing"]["auto_allow"] == {
        "serpbase": False,
        "querit": False,
        "parallel": False,
        "hound": False,
    }


def test_server_normalizes_source_only_auto_allow_preferences():
    config = server._normalize_behavior_config({
        "auto_routing": {
            "provider_priority": ["serpbase", "querit", "brave"],
            "auto_allow": {"serpbase": True, "querit": False},
        }
    })

    assert config["auto_routing"]["provider_priority"][:3] == ["serpbase", "querit", "brave"]
    assert set(config["auto_routing"]["provider_priority"]) == set(server.ROUTING_PROVIDER_ORDER)
    assert config["auto_routing"]["auto_allow"] == {
        "serpbase": True,
        "querit": False,
        "parallel": False,
        "hound": False,
    }
