import time

import pytest

from web_search_plus_mcp import provider_health
from web_search_plus_mcp.http_client import ProviderRequestError


def test_mark_provider_failure_honors_retry_after(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_health, "PROVIDER_HEALTH_FILE", tmp_path / "health.json")

    state = provider_health.mark_provider_failure("tavily", "rate limited", retry_after=900)

    assert state["failure_count"] == 1
    assert state["cooldown_seconds"] == 900
    assert state["cooldown_until"] >= int(time.time()) + 899


def test_mark_provider_failure_caps_retry_after(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_health, "PROVIDER_HEALTH_FILE", tmp_path / "health.json")

    state = provider_health.mark_provider_failure("tavily", "rate limited", retry_after=99999)

    assert state["cooldown_seconds"] == provider_health.COOLDOWN_STEPS_SECONDS[-1]


def test_mark_provider_failure_decays_stale_failure_history(tmp_path, monkeypatch):
    health_file = tmp_path / "health.json"
    monkeypatch.setattr(provider_health, "PROVIDER_HEALTH_FILE", health_file)
    old = int(time.time()) - provider_health.FAILURE_DECAY_SECONDS - 5
    health_file.write_text(
        '{"exa":{"failure_count":3,"cooldown_until":0,"cooldown_seconds":1500,"last_error":"old","last_failure_at":%d}}\n' % old
    )

    state = provider_health.mark_provider_failure("exa", "new")

    assert state["failure_count"] == 1
    assert state["cooldown_seconds"] == provider_health.COOLDOWN_STEPS_SECONDS[0]


def test_execute_provider_with_retry_uses_short_retry_after(monkeypatch):
    sleeps = []
    calls = {"count": 0}
    monkeypatch.setattr(provider_health.time, "sleep", sleeps.append)

    def operation():
        calls["count"] += 1
        if calls["count"] == 1:
            exc = ProviderRequestError("rate limited", status_code=429, transient=True)
            exc.retry_after = 2
            raise exc
        return {"ok": True}

    assert provider_health.execute_provider_with_retry("exa", operation, max_attempts=3) == {"ok": True}
    assert sleeps == [2]
    assert calls["count"] == 2


def test_execute_provider_with_retry_does_not_sleep_long_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr(provider_health.time, "sleep", sleeps.append)

    def operation():
        exc = ProviderRequestError("rate limited", status_code=429, transient=True)
        exc.retry_after = provider_health.MAX_RETRY_AFTER_WAIT_SECONDS + 1
        raise exc

    with pytest.raises(ProviderRequestError):
        provider_health.execute_provider_with_retry("exa", operation, max_attempts=3)
    assert sleeps == []
