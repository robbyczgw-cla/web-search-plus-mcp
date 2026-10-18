"""Extract accepts provider names in any letter case; unknown names fail cleanly."""
import os
from unittest import mock

import pytest

from web_search_plus_mcp import extract

TAVILY_RESULT = {
    "provider": "tavily",
    "results": [{"url": "https://example.com", "title": "T", "content": "tavily page", "raw_content": "tavily page"}],
}


@pytest.mark.parametrize("value", ["Tavily", " tavily ", "TAVILY"])
def test_extract_plus_accepts_provider_in_any_case_or_with_spaces(value):
    with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}, clear=True):
        with mock.patch("web_search_plus_mcp.providers.extract_tavily", return_value=TAVILY_RESULT) as mock_tavily:
            result = extract.extract_plus(["https://example.com"], provider=value)

    mock_tavily.assert_called_once()
    assert result["provider"] == "tavily"
    assert "error" not in result


@pytest.mark.parametrize("value", ["brave", "nope"])
def test_extract_plus_unknown_or_search_only_provider_gives_clean_error(value):
    with mock.patch("web_search_plus_mcp.providers.extract_tavily", side_effect=AssertionError("must not call")):
        result = extract.extract_plus(["https://example.com"], provider=value)

    assert result["results"] == []
    assert "unknown extraction provider" in result["error"]
    assert "tavily" in result["error"]
