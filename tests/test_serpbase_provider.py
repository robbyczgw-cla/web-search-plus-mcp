"""SerpBase mobile/device and source-URL regressions ported from Hermes 5.1.6."""
import io
import json
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

import pytest
from web_search_plus_mcp import providers, http_client, result_redirects, search
from web_search_plus_mcp import config as config_module


def _recorded_shape(name):
    # Live 2026-10-30 response shapes; tokens, session IDs and text sanitised.
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


def test_mobile_recorded_shape_keeps_six_sources_and_drops_two_goto():
    with mock.patch.object(providers, "make_request", return_value=_recorded_shape("serpbase_mobile.json")) as request:
        answer = providers.search_serpbase("python 3.14", "fake", max_results=8)
    assert request.call_args.args[2]["device"] == "mobile"
    result_redirects.clean_result_redirects(answer, config_module._deepcopy_default_config())
    assert len(answer["results"]) == 6
    assert answer["metadata"]["redirects_dropped"] == 2
    assert all("google.com" not in item["url"] for item in answer["results"])


def test_desktop_breadcrumb_shape_prefers_canonical_never_provenance():
    with mock.patch.object(providers, "make_request", return_value=_recorded_shape("serpbase_desktop.json")) as request:
        answer = providers.search_serpbase("python 3.14", "fake", device="desktop")
    assert request.call_args.args[2]["device"] == "desktop"
    first, second, provenance_only = answer["results"]
    assert first["url"] == "https://github.com/python/cpython/blob/3.14/Doc/whatsnew/3.14.rst"
    assert first["source_url"].startswith("https://www.google.com/search")
    # Do not guess repairs or claim to detect 404s; mobile avoids this upstream shape.
    assert second["url"] == "https://docs.python.org/whatsnew/3.14.html"
    assert provenance_only["url"] == ""


@pytest.mark.parametrize("device", ["tablet", "", None, [], 1])
def test_device_config_is_validated(device):
    cfg = config_module._deepcopy_default_config()
    cfg["serpbase"]["device"] = device
    with pytest.raises(ValueError, match="serpbase.device"):
        config_module._validate_runtime_config(cfg)


@pytest.mark.parametrize("device", ["mobile", "desktop"])
def test_device_config_accepts_supported_devices(device):
    cfg = config_module._deepcopy_default_config()
    cfg["serpbase"]["device"] = device
    assert config_module._validate_runtime_config(cfg)["serpbase"]["device"] == device


def test_serpbase_wire_request_uses_wsp_user_agent():
    # Exercise make_request, not a mock of it: urllib's default UA gets blocked.
    response = HTTPError("https://api.serpbase.dev/google/search", 200, "OK", {}, io.BytesIO(b'{"status":0,"organic":[]}'))
    with mock.patch.object(http_client, "urlopen", return_value=response) as open_request:
        providers.search_serpbase("fixture query", "fake")
    request = open_request.call_args.args[0]
    assert request.get_header("User-agent") == http_client.DEFAULT_USER_AGENT
    assert not request.get_header("User-agent").startswith("Python-urllib")
    assert json.loads(request.data)["device"] == "mobile"


def test_device_is_dispatched_and_has_its_own_cache_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPBASE_API_KEY", "fake-serpbase-test-key")
    cfg = config_module._deepcopy_default_config()
    cfg["v3"] = {"cache_dir": str(tmp_path), "state_path": str(tmp_path / "state.sqlite3"),
                 "operator_receipt_journal": False}
    cfg["bounded_context"]["cache_root"] = str(tmp_path)
    devices = []

    def fake_search(**kwargs):
        devices.append(kwargs["device"])
        return {"provider": "serpbase", "query": kwargs["query"], "results": [{
            "title": "Python", "url": "https://www.python.org/", "snippet": "Python reference",
        }]}

    monkeypatch.setattr(providers, "search_serpbase", fake_search)
    first = search.run_search_request(query="python reference", provider="serpbase", config=cfg)
    cached = search.run_search_request(query="python reference", provider="serpbase", config=cfg)
    assert first["results"] and cached["cached"] and devices == ["mobile"]
    cfg["serpbase"]["device"] = "desktop"
    desktop = search.run_search_request(query="python reference", provider="serpbase", config=cfg)
    assert not desktop["cached"] and devices == ["mobile", "desktop"]


