"""Public Provider SDK for Web Search Plus 3.x.

This API is additive-only throughout the 3.x series.  Provider modules should
depend on this package rather than private registry or dispatch modules.
"""

import importlib
import sys

from .api import (
    ExtractExecute,
    ProviderSpec,
    SearchExecute,
    extract_result,
    make_extract_result,
    make_search_result,
    register_provider,
    search_result,
    source_result,
)
from .errors import (
    DuplicateProviderError,
    ProviderConfigError,
    ProviderContractFailure,
    ProviderDiscoveryError,
    ProviderRegistrationError,
    ProviderSDKError,
    ProviderStartupDiagnostic,
)
try:
    from web_search_plus_mcp.http_client import ProviderRequestError
except ImportError:  # pragma: no cover - flat test/script layout
    from http_client import ProviderRequestError

__all__ = [
    "DuplicateProviderError",
    "ExtractExecute",
    "ProviderConfigError",
    "ProviderContractFailure",
    "ProviderDiscoveryError",
    "ProviderRegistrationError",
    "ProviderRequestError",
    "ProviderSDKError",
    "ProviderSpec",
    "ProviderStartupDiagnostic",
    "SearchExecute",
    "extract_result",
    "make_extract_result",
    "make_search_result",
    "register_provider",
    "search_result",
    "source_result",
]

# Submodules reachable under the public name: ``wsp_sdk.<name>``.
_PUBLIC_SUBMODULES = ("api", "conformance", "errors")


def _bind_public_name(name: str = "wsp_sdk") -> None:
    """Make ``name`` and ``name.<submodule>`` resolve to this package's own modules.

    Keeps exactly one object per name in the process, so a provider raises the
    same ``ProviderConfigError`` class the engine's ``isinstance`` checks use.
    Not part of the SDK surface.
    """
    sys.modules[name] = sys.modules[__name__]
    for submodule in _PUBLIC_SUBMODULES:
        sys.modules[f"{name}.{submodule}"] = importlib.import_module(f"{__name__}.{submodule}")
