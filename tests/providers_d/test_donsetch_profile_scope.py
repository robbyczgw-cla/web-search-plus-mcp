"""DonSeTch must honor the host resolver at both subprocess boundaries."""

import shutil
from types import SimpleNamespace

import pytest

from web_search_plus_mcp import credentials, provider_registry


def _module():
    return provider_registry.PROVIDER_SPECS["donsetch"].execute_extract.__globals__


def test_hermes_ignored_file_api_key_never_becomes_an_executable(monkeypatch):
    module = _module()
    binary = shutil.which("true")
    calls = []
    credentials.set_secret_resolver(lambda name, default=None: default)
    def probe(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout="DonSeTch 4.7.0", stderr="")

    monkeypatch.setattr(module["subprocess"], "run", probe)
    config = {"donsetch": {"api_key": binary}}

    report = module["inspect_donsetch_readiness"](config=config)

    assert calls == [], "a file key reported as ignored must never be probed"
    assert report["state"] == "missing"
    assert report["binary_configured"] is False
    with pytest.raises(RuntimeError, match="donsetch_binary_not_configured"):
        module["_resolve_binary"](None, config)


@pytest.mark.parametrize("host_resolver,field", [(False, "api_key"), (False, "binary"), (True, "binary")])
def test_explicit_binary_and_standalone_legacy_path_stay_supported(monkeypatch, host_resolver, field):
    module = _module()
    binary = shutil.which("true")
    calls = []
    if host_resolver:
        credentials.set_secret_resolver(lambda name, default=None: default)

    def probe(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout="DonSeTch 4.7.0", stderr="")

    monkeypatch.setattr(module["subprocess"], "run", probe)
    config = {"donsetch": {field: binary}}
    assert module["_resolve_binary"](None, config) == binary
    report = module["inspect_donsetch_readiness"](config=config)
    assert report["state"] == "executable"
    assert calls == [[binary, "--version"]]


def test_child_env_uses_profile_values_not_process_values(monkeypatch):
    module = _module()
    monkeypatch.setenv("DONSETCH_API_KEY", "other-profile-value")
    monkeypatch.setenv("DONSETCH_PROCESS_ONLY", "must-not-leak")
    monkeypatch.setenv("DONSETCH_TRANSPORT", "http")
    monkeypatch.setenv("UNRELATED_SECRET", "must-not-leak")
    monkeypatch.delenv("DONSETCH_BIN", raising=False)
    scoped = {"DONSETCH_API_KEY": "active-profile-value", "DONSETCH_BIN": "/profile/donsetch"}
    credentials.set_secret_resolver(lambda name, default=None: scoped.get(name, default))

    env = module["_child_env"]()

    assert env["DONSETCH_API_KEY"] == "active-profile-value"
    assert env["DONSETCH_BIN"] == "/profile/donsetch"
    assert "DONSETCH_PROCESS_ONLY" not in env
    assert "UNRELATED_SECRET" not in env
    assert env["DONSETCH_TRANSPORT"] == "stdio"


def test_child_env_propagates_scope_refusal(monkeypatch):
    module = _module()
    monkeypatch.setenv("DONSETCH_API_KEY", "other-profile-value")

    def refuse(name, default=None):
        raise RuntimeError("no active profile")

    credentials.set_secret_resolver(refuse)
    with pytest.raises(RuntimeError, match="no active profile") as caught:
        module["_child_env"]()
    assert credentials.is_secret_scope_error(caught.value)
