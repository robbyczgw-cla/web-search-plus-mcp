import json

from web_search_plus_mcp import cache


def test_cache_stats_counts_only_complete_search_cache_envelopes(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.cache_put("query", "linkup", 3, {"results": ["ok"]})
    (tmp_path / "usage_events.json").write_text('[{"event": "x"}]\n', encoding="utf-8")
    (tmp_path / "provider_stats.json").write_text('{"linkup": []}\n', encoding="utf-8")
    (tmp_path / "unrelated.json").write_text(
        json.dumps({"owner": "host", "_cache_timestamp": 1}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "corrupt.json").write_text("{not json", encoding="utf-8")

    stats = cache.cache_stats()

    assert stats["total_entries"] == 1
    assert stats["providers"] == {"linkup": 1}


def test_cache_clear_preserves_foreign_json_byte_for_byte(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.cache_put("query", "linkup", 3, {"results": ["ok"]})
    foreign_payloads = {
        "usage_events.json": b'[{"event": "x"}]\n',
        "provider_stats.json": b'{"linkup": []}\n',
        "provider_health.json": b'{"keep": true}\n',
        "unrelated.json": b'{"owner": "host", "_cache_timestamp": 1}\n',
        "corrupt.json": b"{not json",
        "binary.json": b"\xff\xfe\x00not-utf8",
    }
    for name, payload in foreign_payloads.items():
        (tmp_path / name).write_bytes(payload)

    result = cache.cache_clear()

    assert result["cleared"] == 1
    for name, payload in foreign_payloads.items():
        assert (tmp_path / name).read_bytes() == payload


def test_cache_stats_ignores_invalid_utf8_foreign_json(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.cache_put("query", "serper", 2, {"results": ["ok"]})
    invalid = tmp_path / "binary.json"
    invalid.write_bytes(b"\xff\xfe\x00not-utf8")

    stats = cache.cache_stats()

    assert stats["total_entries"] == 1
    assert invalid.read_bytes() == b"\xff\xfe\x00not-utf8"
