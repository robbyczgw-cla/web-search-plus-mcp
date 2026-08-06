import importlib
import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    tomllib = importlib.import_module("tomli")


ROOT = Path(__file__).resolve().parents[1]


def load_json(name):
    return json.loads((ROOT / name).read_text())


def project_version():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return project["project"]["version"]


def test_plugin_manifest_matches_current_package_and_portable_contract():
    manifest = load_json("plugin.json")
    version = project_version()

    assert set(manifest) <= {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
    assert manifest["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    assert re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", manifest["name"])
    assert "--" not in manifest["name"]
    assert ".." not in manifest["name"]
    assert manifest["version"] == version
    assert manifest["license"] == "MIT"
    assert manifest["repository"].startswith("https://github.com/")
    assert manifest["homepage"].startswith("https://")
    assert manifest["keywords"]


def test_mcp_manifest_pins_the_published_package_without_secrets():
    manifest = load_json("mcp.json")
    version = project_version()
    server = manifest["mcpServers"]["web-search-plus"]

    assert set(manifest) == {"$schema", "mcpServers"}
    assert manifest["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    )
    assert set(manifest["mcpServers"]) == {"web-search-plus"}
    assert server == {
        "type": "stdio",
        "command": "uvx",
        "args": [
            "--from",
            f"web-search-plus-mcp=={version}",
            "web-search-plus-mcp",
        ],
    }
    assert "env" not in server
    assert not re.search(
        r"(?:api[_-]?key|token|secret|password)",
        json.dumps(manifest),
        flags=re.I,
    )


def test_agent_plugin_files_are_root_level_package_boundaries():
    assert (ROOT / "plugin.json").is_file()
    assert (ROOT / "mcp.json").is_file()
    assert (ROOT / "plugin.json").parent == ROOT
    assert (ROOT / "mcp.json").parent == ROOT


def test_readme_documents_the_portable_agent_plugins_package():
    readme = (ROOT / "README.md").read_text()

    assert "Agent Plugins 1.0" in readme
    assert "[`plugin.json`](plugin.json)" in readme
    assert "[`mcp.json`](mcp.json)" in readme
    assert "exact `web-search-plus-mcp` version pin" in readme
    assert "Provider credentials are deliberately not stored" in readme
