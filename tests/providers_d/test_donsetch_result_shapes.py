"""DonSeTch result shapes: split (structuredContent) and folded (`[meta]` in content).

The fixtures are real tools/call results captured from DonSeTch 4.7.0 and 4.10.1
(trimmed to three hits and short debug fields). 4.10.1 folds the result for
clients it does not recognize unless DONSETCH_MCP__TEXT_ONLY=false is set.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from web_search_plus_mcp import provider_registry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "donsetch"
TRUE_BIN = shutil.which("true") or "/bin/true"
SPLIT = ["donsetch_470_split", "donsetch_4101_text_only_false_split"]
FOLDED = ["donsetch_4101_default_folded"]
SEARCH_URLS = [
    "https://docs.python.org/3/whatsnew/3.14.html",
    "https://docs.python.org/3/whatsnew/3.15.html",
    "https://stackoverflow.com/questions/73908268/python-polars-are-there-any-updated-release-notes-for-new-versions",
]


def _module():
    spec = provider_registry.PROVIDER_SPECS["donsetch"]
    return spec, spec.execute_search.__globals__


def _fixture(name, kind):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))[kind]


def _args():
    return SimpleNamespace(
        query="python release notes", max_results=3, search_type="search", time_range=None,
        freshness=None, images=False, include_domains=[], exclude_domains=[], category=None,
    )


def _search(monkeypatch, result):
    spec, module = _module()
    payload = module["_payload_from_tool_result"](result)
    monkeypatch.setitem(module, "_call_donsetch_tool", lambda *_a: payload)
    return spec.execute_search(None, "donsetch", _args(), TRUE_BIN, {"donsetch": {"timeout": 30}}, {})


def _extract(monkeypatch, result, url="https://example.com"):
    spec, module = _module()
    payload = module["_payload_from_tool_result"](result)

    class Session:
        def __init__(self, *_a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def call(self, _tool, _arguments):
            return payload

    monkeypatch.setitem(module, "DonsetchSession", Session)
    return spec.execute_extract(
        None, "donsetch", [url], TRUE_BIN, "markdown", False, False, False,
        {"donsetch": {"timeout": 30}}, False,
    )


def test_child_env_forces_split_shape_over_operator_value(monkeypatch):
    _spec, module = _module()
    monkeypatch.delenv("DONSETCH_MCP__TEXT_ONLY", raising=False)
    assert module["_child_env"]()["DONSETCH_MCP__TEXT_ONLY"] == "false"
    # An operator value (process env or profile) must not switch the adapter back to the fold.
    monkeypatch.setenv("DONSETCH_MCP__TEXT_ONLY", "true")
    monkeypatch.setitem(module, "get_secret", lambda name, default=None: "true" if name == "DONSETCH_MCP__TEXT_ONLY" else default)
    env = module["_child_env"]()
    assert env["DONSETCH_MCP__TEXT_ONLY"] == "false"
    assert os.environ["DONSETCH_MCP__TEXT_ONLY"] == "true"


@pytest.mark.parametrize("name", SPLIT + FOLDED)
def test_search_fixture_projects_three_results(monkeypatch, name):
    result = _search(monkeypatch, _fixture(name, "search"))
    assert [item["url"] for item in result["results"]] == SEARCH_URLS
    assert result["results"][0]["title"].startswith("What’s new in Python 3.14")
    assert result["results"][0]["snippet"]
    assert "[meta]" not in json.dumps(result)


@pytest.mark.parametrize("name", SPLIT + FOLDED)
def test_extract_fixture_projects_page(monkeypatch, name):
    result = _extract(monkeypatch, _fixture(name, "extract"))
    item = result["results"][0]
    assert not item.get("error")
    assert item["url"] == "https://example.com/"
    assert item["title"] == "Example Domain"
    assert item["content"].startswith("# Example Domain")
    assert "[meta]" not in item["content"]


def test_folded_payload_equals_split_payload_content():
    _spec, module = _module()
    for kind in ("search", "extract"):
        split = module["_payload_from_tool_result"](_fixture("donsetch_4101_text_only_false_split", kind))
        folded = module["_payload_from_tool_result"](_fixture("donsetch_4101_default_folded", kind))
        assert folded["structured"].keys() == split["structured"].keys()
        assert folded["text"].splitlines()[0] == split["text"].splitlines()[0]


def test_folded_meta_in_a_single_joined_string_is_also_read():
    # Some MCP bridges join the content blocks into one string.
    _spec, module = _module()
    result = {"content": '[meta] {"ok":true,"results":[]}\n\n# Search results\n'}
    payload = module["_payload_from_tool_result"](result)
    assert payload["structured"] == {"ok": True, "results": []}
    assert payload["text"] == "# Search results\n"


def test_structured_content_wins_over_a_meta_line():
    _spec, module = _module()
    result = {
        "structuredContent": {"ok": True, "results": [{"url": "https://a.example/"}]},
        "content": [{"type": "text", "text": '[meta] {"ok":true,"results":[]}\n\nbody'}],
    }
    payload = module["_payload_from_tool_result"](result)
    assert payload["structured"]["results"] == [{"url": "https://a.example/"}]
    assert payload["text"].startswith("[meta]")


@pytest.mark.parametrize(
    "text",
    [
        "[meta] {not json}\n\n1. Sabc · T : a.example",
        '[meta] ["list"]\n\nbody',
        '[meta] {"results":[]}\n\nbody',  # no boolean ok
        '[meta] {"ok":"yes"}\n\nbody',
        "[meta]\n\nbody",
        'body first\n[meta] {"ok":true,"results":[]}',  # not the leading line
        "",
    ],
)
def test_malformed_meta_keeps_the_contract_error(monkeypatch, text):
    result = {"content": [{"type": "text", "text": text}]}
    with pytest.raises(RuntimeError, match="donsetch_search_contract_failed"):
        _search(monkeypatch, result)


def test_malformed_meta_text_is_left_intact():
    _spec, module = _module()
    payload = module["_payload_from_tool_result"]({"content": [{"type": "text", "text": "[meta] {oops\nbody"}]})
    assert payload["structured"] == {}
    assert payload["text"] == "[meta] {oops\nbody"


def test_folded_meta_without_results_is_a_search_contract_error(monkeypatch):
    result = {"content": [{"type": "text", "text": '[meta] {"ok":true}\n\n'}, {"type": "text", "text": "# Search results"}]}
    with pytest.raises(RuntimeError, match="donsetch_search_contract_failed"):
        _search(monkeypatch, result)


def test_extract_with_malformed_meta_does_not_invent_a_page(monkeypatch):
    result = {"content": [{"type": "text", "text": "[meta] {oops"}, {"type": "text", "text": "# Page\n\nbody"}]}
    item = _extract(monkeypatch, result)["results"][0]
    assert item.get("error")
    assert not item.get("content")


def test_folded_failed_fetch_keeps_its_error():
    _spec, module = _module()
    meta = {"ok": False, "content_ok": False, "code": "network.dns", "errorKind": "transient", "next_action": "retry later", "url": "https://x.example/"}
    result = {"content": [{"type": "text", "text": "[meta] " + json.dumps(meta) + "\n\n"}, {"type": "text", "text": "failed"}]}
    payload = module["_payload_from_tool_result"](result)
    item = module["_project_fetch_item"](payload, "https://x.example/")
    assert item.get("error")
