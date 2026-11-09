"""Environment file compatibility at the MCP/host boundary; no providers run."""
from types import SimpleNamespace
import sys

import pytest

from web_search_plus_mcp import env_loader


@pytest.mark.parametrize("host_state", ["missing", "refuses", "invalid_path", "profile"])
def test_env_loading_preserves_precedence_and_host_fallback(tmp_path, monkeypatch, host_state):
    package = tmp_path / "install" / "package"
    package.mkdir(parents=True)
    profile = tmp_path / "profile"
    profile.mkdir()
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fallback))

    def get_hermes_home():
        if host_state == "refuses":
            raise RuntimeError("host profile not available")
        return None if host_state == "invalid_path" else profile

    monkeypatch.setitem(sys.modules, "hermes_constants", None if host_state == "missing" else SimpleNamespace(get_hermes_home=get_hermes_home))
    local = package / ".env"
    parent = package.parent / ".env"
    selected_profile = (profile if host_state == "profile" else fallback) / ".env"
    local.write_text("# comment\nmalformed line\n=ignored\nexport FIRST=local\nPROFILE=your_api_key\nKEEP=local\nQUOTED=\"'\"****\"'\"\nRAW=\"'\"real-key\"'\"\n")
    parent.write_text("FIRST=parent\nSECOND=parent\nPROFILE=***\nEQUALS=part=two\n")
    selected_profile.write_text("FIRST=profile\nSECOND=profile\nPROFILE=profile-real-key\nQUOTED=profile-quoted-key\n")
    environ = {"KEEP": "process"}

    loaded = env_loader.load_env_files(package / "server.py", environ)

    assert loaded == [local, parent, selected_profile]
    assert environ == {
        "KEEP": "process", "FIRST": "local", "SECOND": "parent",
        "PROFILE": "profile-real-key", "QUOTED": "profile-quoted-key",
        "RAW": '\"real-key\"', "EQUALS": "part=two",
    }


def test_env_loading_reads_a_shared_parent_and_profile_only_once(tmp_path, monkeypatch):
    package = tmp_path / "package"
    package.mkdir()
    monkeypatch.setitem(sys.modules, "hermes_constants", SimpleNamespace(get_hermes_home=lambda: tmp_path))
    shared = tmp_path / ".env"
    shared.write_text("KEY=real-value\n")
    environ = {}

    assert env_loader.load_env_files(package / "server.py", environ) == [shared]
    assert environ == {"KEY": "real-value"}
