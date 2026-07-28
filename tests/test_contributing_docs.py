from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "CONTRIBUTING.md"


def test_contribution_guide_covers_mcp_contracts() -> None:
    assert GUIDE.is_file(), "CONTRIBUTING.md is missing"
    text = GUIDE.read_text(encoding="utf-8")

    required = (
        "## Project boundaries",
        "## Local setup",
        "## Required checks",
        "## Portable engine changes",
        "## Provider changes",
        "## Security and privacy",
        "## Pull requests",
        "web_search",
        "web_extract",
        "source-only",
        "CHANGELOG.md",
    )
    for marker in required:
        assert marker in text, f"missing contribution-guide contract: {marker}"


def test_contribution_guide_matches_ci_commands() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    commands = (
        'python -m pip install -e ".[test]"',
        "python -m pytest tests/ -q -p no:cacheprovider",
        "ruff check --config pyproject.toml .",
        "python -m compileall -q web_search_plus_mcp tests",
        "python -m build",
    )
    for command in commands:
        assert command in workflow, f"CI no longer runs documented command: {command}"
        assert command in guide, f"guide does not document CI command: {command}"


def test_contribution_guide_is_linked_and_internal_links_resolve() -> None:
    assert "CONTRIBUTING.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    text = GUIDE.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if path:
            assert (ROOT / path).exists(), f"broken internal link: {target}"
