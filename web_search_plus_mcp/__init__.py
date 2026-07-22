"""Web Search Plus MCP package."""

from pathlib import Path
import sys


# The upstream runtime is also executable as a standalone ``search.py`` script
# and therefore keeps flat intra-runtime imports. Make that module directory
# importable when the same runtime is loaded through the MCP Python package.
_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

__version__ = "1.2.0"
