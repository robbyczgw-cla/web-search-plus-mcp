"""Tests for the optional web UI module."""

import json
from unittest import mock

import pytest

with mock.patch.dict(
    "sys.modules",
    {"fastapi": mock.MagicMock(), "fastapi.responses": mock.MagicMock(), "fastapi.staticfiles": mock.MagicMock(), "uvicorn": mock.MagicMock(), "pydantic": mock.MagicMock()},
):
    pass  # UI tests import fastapi normally at runtime

from fastapi.testclient import TestClient

from web_search_plus_mcp import __version__
from web_search_plus_mcp.ui import create_app


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv("WEB_SEARCH_PLUS_CONFIG", str(config_path))
    return config_path


def test_index_served():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Web Search Plus" in response.text


def test_version_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json()["version"] == __version__


def test_get_config_defaults(temp_config):
    client = TestClient(create_app())
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["config_path"] == str(temp_config)
    assert "config" in data
    assert "defaults" in data


def test_post_config_requires_csrf(temp_config):
    client = TestClient(create_app())
    response = client.post("/api/config", json={"auto_routing": {"disabled_providers": ["firecrawl"]}})
    assert response.status_code == 403


def test_post_config_valid(temp_config):
    client = TestClient(create_app())
    csrf = client.get("/api/csrf")
    token = csrf.json()["csrf_token"]
    response = client.post(
        "/api/config",
        json={"auto_routing": {"disabled_providers": ["firecrawl"]}},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    saved = json.loads(temp_config.read_text())
    assert "firecrawl" in saved["auto_routing"]["disabled_providers"]


def test_post_config_unknown_provider_rejected(temp_config):
    client = TestClient(create_app())
    csrf = client.get("/api/csrf")
    token = csrf.json()["csrf_token"]
    response = client.post(
        "/api/config",
        json={"auto_routing": {"disabled_providers": ["not-a-provider"]}},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 422


def test_post_config_creates_backup(temp_config):
    temp_config.write_text(json.dumps({"version": 1}))
    client = TestClient(create_app())
    csrf = client.get("/api/csrf")
    token = csrf.json()["csrf_token"]
    response = client.post(
        "/api/config",
        json={"auto_routing": {"disabled_providers": ["firecrawl"]}},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    backups = list(temp_config.parent.glob("config.json.bak.*"))
    assert backups


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_stats_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_providers_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert "tavily" in data
    assert "capabilities" in data["tavily"]


def test_doctor_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/doctor")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
