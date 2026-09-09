import socket
import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "web_search_plus_mcp"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))


@pytest.fixture(autouse=True)
def _example_com_dns_fixture(monkeypatch):
    """Mock only the public example.com host used by mocked extraction tests.

    Keep URL/IP security validation enabled, without requiring live DNS. Safety
    tests can still replace getaddrinfo themselves to exercise private addresses,
    resolution errors and rebinding. All other hosts retain the real resolver.
    """
    resolve = socket.getaddrinfo

    def fixture_address(host, port, *args, **kwargs):
        if host == "example.com":
            host = "93.184.216.34"  # Public-address fixture, not a live DNS claim.
        return resolve(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fixture_address)


@pytest.fixture(autouse=True)
def _isolate_runtime_cache(tmp_path, monkeypatch):
    """Keep v3 response/state caches from leaking between unit tests."""
    from web_search_plus_mcp import cache, orchestrator_v3, provider_health, provider_stats

    cache_root = tmp_path / "wsp-cache"
    monkeypatch.setattr(cache, "CACHE_DIR", cache_root)
    monkeypatch.setattr(orchestrator_v3.legacy_cache, "CACHE_DIR", cache_root)
    monkeypatch.setattr(provider_health, "CACHE_DIR", cache_root)
    monkeypatch.setattr(provider_health, "PROVIDER_HEALTH_FILE", cache_root / "provider_health.json")
    monkeypatch.setattr(provider_stats, "CACHE_DIR", cache_root)
    monkeypatch.setattr(provider_stats, "PROVIDER_STATS_FILE", cache_root / "provider_stats.json")
