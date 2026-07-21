"""Regression tests for the v1.1.1 fixes (spans projection, wsp_sdk import)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from web_search_plus_mcp import server

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_extract_projection_preserves_spans():
    payload = {
        "results": [
            {
                "url": "https://example.com/doc",
                "text": "full cleaned text",
                "spans": [
                    {"start": 0, "end": 4, "text": "full", "within_preview": True},
                    "not-a-span",
                ],
                "span_contract_version": 1,
            },
            {"url": "https://example.com/plain", "text": "no spans here"},
        ],
    }

    projected = server._project_v3_payload(
        payload, capability="extract", urls=["https://example.com/doc"]
    )

    first, second = projected["results"]
    assert first["spans"] == [
        {"start": 0, "end": 4, "text": "full", "within_preview": True}
    ]
    assert first["span_contract_version"] == 1
    assert "spans" not in second


def test_wsp_sdk_imports_as_plain_package_without_path_hacks():
    result = subprocess.run(
        [sys.executable, "-c", "import wsp_sdk; print(wsp_sdk.ProviderSpec.__name__)"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ProviderSpec"
