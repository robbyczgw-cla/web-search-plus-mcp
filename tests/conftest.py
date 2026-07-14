import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "web_search_plus_mcp"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))


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
