import gzip
import json
import zlib

import pytest

import web_search_plus_mcp.search as search


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def read(self):
        return self.payload

    def getheader(self, name):
        return self.headers.get(name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_read_json_response_decompresses_gzip_header():
    body = {"web": {"results": []}}
    compressed = gzip.compress(json.dumps(body).encode("utf-8"))

    result = search._read_json_response(
        FakeResponse(compressed, {"Content-Encoding": "gzip"})
    )

    assert result == body


def test_read_json_response_decompresses_gzip_magic_without_header():
    body = {"ok": True}
    compressed = gzip.compress(json.dumps(body).encode("utf-8"))

    result = search._read_json_response(FakeResponse(compressed, {}))

    assert result == body


def test_read_json_response_decompresses_deflate_header():
    body = {"ok": "deflate"}
    compressed = zlib.compress(json.dumps(body).encode("utf-8"))

    result = search._read_json_response(
        FakeResponse(compressed, {"Content-Encoding": "deflate"})
    )

    assert result == body


def test_read_json_response_rejects_brotli_header():
    with pytest.raises(search.ProviderRequestError, match="Brotli-compressed response"):
        search._read_json_response(FakeResponse(b"not-json", {"Content-Encoding": "br"}))


def test_make_get_request_handles_gzip_urllib_response(monkeypatch):
    body = {"web": {"results": [{"title": "Brave works"}]}}
    compressed = gzip.compress(json.dumps(body).encode("utf-8"))

    def fake_urlopen(req, timeout):
        return FakeResponse(compressed, {"Content-Encoding": "gzip"})

    monkeypatch.setattr(search, "urlopen", fake_urlopen)

    result = search.make_get_request(
        "https://api.search.brave.com/res/v1/web/search?q=test",
        {"Accept": "application/json", "X-Subscription-Token": "test"},
    )

    assert result == body


def test_make_request_handles_gzip_urllib_response(monkeypatch):
    body = {"organic": [{"title": "POST works"}]}
    compressed = gzip.compress(json.dumps(body).encode("utf-8"))

    def fake_urlopen(req, timeout):
        return FakeResponse(compressed, {"Content-Encoding": "gzip"})

    monkeypatch.setattr(search, "urlopen", fake_urlopen)

    result = search.make_request(
        "https://example.test/search",
        {"Accept": "application/json"},
        {"q": "test"},
    )

    assert result == body
