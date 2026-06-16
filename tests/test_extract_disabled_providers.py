"""Tests for extract_plus respecting disabled_providers from config.json."""

import os
from unittest import mock

import web_search_plus_mcp.extract as extract


def test_extract_plus_auto_skips_disabled_providers():
    config = {
        "auto_routing": {
            "disabled_providers": ["firecrawl"],
            "provider_priority": ["tavily", "exa", "linkup", "parallel", "firecrawl", "you"],
        }
    }
    with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test", "FIRECRAWL_API_KEY": "fc-test"}, clear=True):
        with mock.patch.object(extract, "extract_tavily", return_value={"provider": "tavily", "results": []}) as mock_tavily:
            with mock.patch.object(extract, "extract_firecrawl") as mock_firecrawl:
                result = extract.extract_plus(["https://example.com"], provider="auto", config=config)

    assert result["provider"] == "tavily"
    mock_tavily.assert_called_once()
    mock_firecrawl.assert_not_called()


def test_extract_plus_explicit_disabled_provider_is_still_tried():
    config = {
        "auto_routing": {
            "disabled_providers": ["firecrawl"],
            "provider_priority": ["tavily", "exa", "linkup", "parallel", "firecrawl", "you"],
        }
    }
    with mock.patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test", "LINKUP_API_KEY": "linkup-test"}, clear=True):
        with mock.patch.object(extract, "extract_firecrawl", return_value={"provider": "firecrawl", "results": [{"url": "https://example.com", "error": "fetch failed"}]}) as mock_firecrawl:
            with mock.patch.object(extract, "extract_linkup", return_value={"provider": "linkup", "results": [{"url": "https://example.com", "content": "fallback"}]}) as mock_linkup:
                result = extract.extract_plus(["https://example.com"], provider="firecrawl", config=config)

    assert result["provider"] == "linkup"
    mock_firecrawl.assert_called_once()
    mock_linkup.assert_called_once()
