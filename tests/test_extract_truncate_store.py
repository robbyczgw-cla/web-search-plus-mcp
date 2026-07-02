from pathlib import Path

import web_search_plus_mcp.cache as cache
import web_search_plus_mcp.extract as extract


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


def test_truncate_and_store_extracts_bounds_large_mcp_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(extract, "store_web_text", cache.store_web_text)
    full_text = "A" * 500
    result = {
        "provider": "tavily",
        "results": [
            {"url": "https://example.com/large", "content": full_text},
            {"url": "https://example.com/small", "content": "small"},
        ],
    }

    bounded = extract._truncate_and_store_extracts(result, preview_chars=12)

    assert bounded["extract_storage"] == {"stored": 1, "preview_chars": 12}
    large = bounded["results"][0]
    assert large["content"].startswith("A" * 12)
    assert len(large["content"]) < len(full_text)
    assert large["stored_extract"]["stored"] is True
    assert large["stored_extract"]["field"] == "content"
    assert Path(large["stored_extract"]["path"]).exists()
    assert bounded["results"][1] == {"url": "https://example.com/small", "content": "small"}
