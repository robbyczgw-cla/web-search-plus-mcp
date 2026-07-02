import io
import json
import socket
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

import web_search_plus_mcp
import web_search_plus_mcp.http_client as http_client


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


def test_default_user_agent_tracks_package_version():
    assert http_client.DEFAULT_USER_AGENT == f"ClawdBot-WebSearchPlus-MCP/{web_search_plus_mcp.__version__}"
    assert http_client.DEFAULT_USER_AGENT.endswith("/0.15.0")


@pytest.mark.parametrize(
    ("payload", "headers", "message"),
    [
        (b"not-gzip", {"Content-Encoding": "gzip"}, "corrupted gzip"),
        (b"not-deflate", {"Content-Encoding": "deflate"}, "corrupted deflate"),
        ("ä".encode("latin-1"), {}, "non-UTF-8"),
        (b"not-json", {}, "invalid JSON"),
    ],
)
def test_read_json_response_hardens_provider_body_errors(payload, headers, message):
    with pytest.raises(http_client.ProviderRequestError, match=message) as exc:
        http_client._read_json_response(FakeResponse(payload, headers))

    assert exc.value.transient is True


def test_http_429_retry_after_is_exposed_as_provider_metadata():
    body = json.dumps({"error": "slow down"}).encode("utf-8")
    headers = Message()
    headers["Retry-After"] = "7"
    err = HTTPError("https://example.test", 429, "Too Many", headers, io.BytesIO(body))

    with pytest.raises(http_client.ProviderRequestError) as exc:
        http_client._raise_provider_http_error(err)

    assert exc.value.status_code == 429
    assert exc.value.transient is True
    assert exc.value.retry_after == 7.0


def test_urlerror_socket_timeout_is_transient(monkeypatch):
    def fake_urlopen(req, timeout):
        raise URLError(socket.timeout("timed out"))

    monkeypatch.setattr(http_client, "urlopen", fake_urlopen)

    with pytest.raises(http_client.ProviderRequestError) as exc:
        http_client.make_get_request("https://example.test", {})

    assert exc.value.transient is True
