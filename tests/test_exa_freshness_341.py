from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

from web_search_plus_mcp import provider_dispatch, providers


def test_exa_freshness_is_supported_and_maps_to_canonical_value():
    assert providers.provider_supports_freshness("exa") is True
    assert providers.map_freshness_for_provider("exa", "week") == "week"


def test_exa_freshness_uses_absolute_utc_bounds():
    start, end = providers.exa_date_bounds(
        "week",
        now=datetime(2026, 7, 25, 12, 34, 56, tzinfo=timezone.utc),
    )
    assert start == "2026-07-18T12:34:56Z"
    assert end == "2026-07-25T12:34:56Z"
    hour_start, hour_end = providers.exa_date_bounds(
        "hour",
        now=datetime(2026, 7, 25, 12, 34, 56, tzinfo=timezone.utc),
    )
    assert hour_start == "2026-07-25T11:34:56Z"
    assert hour_end == "2026-07-25T12:34:56Z"


def test_exa_freshness_metadata_reports_native_date_range():
    with mock.patch.object(
        providers,
        "exa_date_bounds",
        return_value=("2026-07-18T12:34:56Z", "2026-07-25T12:34:56Z"),
    ) as bounds:
        metadata = providers.freshness_metadata("exa", "week")
    bounds.assert_called_once_with("week")
    assert metadata == {
        "requested": "week",
        "applied": True,
        "provider": "exa",
        "native_value": {
            "startPublishedDate": "2026-07-18T12:34:56Z",
            "endPublishedDate": "2026-07-25T12:34:56Z",
        },
    }


def test_exa_freshness_metadata_reports_explicit_date_overrides():
    with mock.patch.object(
        providers,
        "exa_date_bounds",
        return_value=("2026-07-18T12:34:56Z", "2026-07-25T12:34:56Z"),
    ):
        metadata = providers.freshness_metadata(
            "exa",
            "week",
            start_date="2020-01-01T00:00:00Z",
        )
    assert metadata["native_value"] == {
        "startPublishedDate": "2020-01-01T00:00:00Z",
        "endPublishedDate": "2026-07-25T12:34:56Z",
    }


def test_exa_request_applies_freshness_but_explicit_dates_win(monkeypatch):
    captured = []

    def fake_post(url, headers, body, timeout=30):
        captured.append(body)
        return {"results": []}

    monkeypatch.setattr(providers, "make_request", fake_post)
    monkeypatch.setattr(
        providers,
        "exa_date_bounds",
        lambda freshness: ("2026-07-18T12:34:56Z", "2026-07-25T12:34:56Z"),
    )

    providers.search_exa(query="q", api_key="exa-key", freshness="week")
    providers.search_exa(
        query="q",
        api_key="exa-key",
        freshness="week",
        start_date="2020-01-01T00:00:00Z",
        end_date="2020-01-31T00:00:00Z",
    )

    assert captured[0]["startPublishedDate"] == "2026-07-18T12:34:56Z"
    assert captured[0]["endPublishedDate"] == "2026-07-25T12:34:56Z"
    assert captured[1]["startPublishedDate"] == "2020-01-01T00:00:00Z"
    assert captured[1]["endPublishedDate"] == "2020-01-31T00:00:00Z"


def test_exa_dispatch_forwards_freshness():
    calls = []

    def search_exa(**kwargs):
        calls.append(kwargs)
        return {"results": []}

    args = SimpleNamespace(
        query="q",
        max_results=5,
        exa_type="neural",
        category=None,
        start_date=None,
        end_date=None,
        similar_url=None,
        include_domains=None,
        exclude_domains=None,
        exa_verbosity="standard",
        freshness="week",
    )
    provider_dispatch.SEARCH_DISPATCH["exa"](
        {"search_exa": search_exa},
        "exa",
        args,
        "key",
        {},
        {},
    )

    assert calls[0]["freshness"] == "week"
    assert calls[0]["start_date"] is None
    assert calls[0]["end_date"] is None
