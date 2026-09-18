from __future__ import annotations

from web_search_plus_mcp.config import DEFAULT_CONFIG, _deepcopy_default_config, _validate_runtime_config
from web_search_plus_mcp.jev_optional import (
    extract_item_action,
    filter_extract_results,
    keyword_vertical,
    maybe_fill_language,
    maybe_search_type,
    settings_from_config,
)


def test_default_config_jev_is_off():
    jev = DEFAULT_CONFIG["jev"]
    assert jev["enabled"] is False
    assert jev["search_type"] is False
    assert jev["extract_quality"] is False
    assert jev["language_fill"] is False
    assert settings_from_config(_deepcopy_default_config()).enabled is False


def test_validate_runtime_rejects_api_key_in_config():
    cfg = _deepcopy_default_config()
    cfg["jev"]["api_key"] = "nope"
    try:
        _validate_runtime_config(cfg)
    except ValueError as exc:
        assert "api_key" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_disabled_extract_keeps_cloudflare_page():
    content = "Just a moment... Checking your browser. Ray ID 123."
    action, meta = extract_item_action(content, config=_deepcopy_default_config())
    assert action == "keep"
    assert meta is None


def _on(**flags):
    cfg = _deepcopy_default_config()
    cfg["jev"]["enabled"] = True
    for key, value in flags.items():
        cfg["jev"][key] = value
    return cfg


def test_extract_regex_rejects_short_challenge_without_jev():
    content = "Just a moment... Checking your browser. Ray ID 123."
    action, meta = extract_item_action(content, config=_on(extract_quality=True))
    assert action == "reject"
    assert meta["backend"] == "regex"


def test_extract_jev_overrides_long_captcha_article():
    body = (
        "Researchers studied how CAPTCHA and hCaptcha affect checkout conversion. "
        * 20
    )

    def chooser(**kwargs):
        return "usable_content", 0.94

    action, meta = extract_item_action(
        body, query="captcha conversion study", config=_on(extract_quality=True), chooser=chooser
    )
    assert action == "keep"
    assert meta["backend"] == "jev"
    assert meta["overrode"] == "blocked_or_challenge"


def test_language_fill_only_when_wsp_none():
    def chooser(**kwargs):
        return "de", 0.96

    filled, meta = maybe_fill_language(
        "Linzer Torte Rezept", "de", config=_on(language_fill=True), chooser=chooser
    )
    assert filled == "de"
    assert meta is None

    filled, meta = maybe_fill_language(
        "Linzer Torte Rezept", None, config=_on(language_fill=True), chooser=chooser
    )
    assert filled == "de"
    assert meta["applied"] is True


def test_search_type_overlay_confirms_news_at_095():
    def chooser(**kwargs):
        return "news", 0.97

    label, meta = maybe_search_type(
        "breaking news Wien", "search", config=_on(search_type=True), chooser=chooser
    )
    assert label == "news"
    assert meta["applied"] == "news"


def test_search_type_overlay_falls_back_below_095():
    def chooser(**kwargs):
        return "news", 0.90

    label, meta = maybe_search_type(
        "press briefing Raft consensus", "search", config=_on(search_type=True), chooser=chooser
    )
    assert label == "search"
    assert meta["applied"] == "search"


def test_keyword_vertical_news_and_search():
    assert keyword_vertical("breaking news Wien") == "news"
    assert keyword_vertical("python asyncio tutorial") == "search"


def test_filter_extract_fallback_when_all_rejected():
    results = [{"url": "https://example.com", "content": "Just a moment Checking your browser Ray ID 99"}]
    kept, meta = filter_extract_results(results, config=_on(extract_quality=True))
    assert kept == []
    assert meta["kept"] == 0


def test_validate_runtime_config_accepts_jev_defaults():
    cfg = _deepcopy_default_config()
    out = _validate_runtime_config(cfg)
    assert out["jev"]["enabled"] is False
    assert out["jev"]["search_type"] is False
