"""wsp_sdk and its submodules resolve to one object per name in the MCP package.

A provider in providers.d raises ``wsp_sdk.errors.ProviderConfigError``; the
engine's isinstance checks must see the same class, or a missing key turns into
an unclassified failure.
"""

from __future__ import annotations

import subprocess
import sys

CHECK = """
import sys
import web_search_plus_mcp.provider_registry as registry
import wsp_sdk, wsp_sdk.api, wsp_sdk.errors, wsp_sdk.conformance
from web_search_plus_mcp import errors_v3

registry._publish_sdk()
assert sys.modules["wsp_sdk"] is wsp_sdk
for name in ("api", "errors", "conformance"):
    assert sys.modules["wsp_sdk." + name] is getattr(wsp_sdk, name), name
assert errors_v3.ProviderConfigError is wsp_sdk.errors.ProviderConfigError
specs, diagnostics = registry.discover_providers()
assert not diagnostics, diagnostics
assert "tinyfish" in {spec.provider for spec in specs}
print("ok")
"""


def test_sdk_submodules_are_one_object_per_name(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-c", CHECK],
        capture_output=True, text=True, cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_conformance_does_not_load_unittest_mock_at_import(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-c", "import sys, wsp_sdk.conformance; print('unittest.mock' in sys.modules)"],
        capture_output=True, text=True, cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False"
