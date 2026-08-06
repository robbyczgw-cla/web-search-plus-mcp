# web-search-plus-mcp 3.6.0 release notes

`web-search-plus-mcp 3.6.0` adds a portable Agent Plugins 1.0 packaging layer while keeping the existing MCP server, tools, and PyPI distribution model.

## Highlights

- Add root-level `plugin.json` and `mcp.json` manifests for Agent Plugins 1.0 clients.
- Start the published MCP server through `uvx` with an exact `web-search-plus-mcp==3.6.0` pin.
- Keep PyPI as the runtime source of truth; no second Python package or central marketplace is introduced.
- Keep provider credentials outside the manifests so clients provide them through the process environment.

## Compatibility and upgrade

- Python `>=3.10` remains supported.
- The stable MCP tools remain `web_search` and `web_extract`.
- Existing MCP SDK-v2 stdio compatibility from 3.5.0 remains unchanged, including modern `2026-07-28` and legacy `2025-11-25` negotiation paths.
- For Agent Plugins clients, load the repository root as a portable plugin and ensure `uv` is installed.
- Upgrade the Python package with:

  ```bash
  pip install --upgrade "web-search-plus-mcp==3.6.0"
  ```

## Security boundary

The plugin manifests contain no API keys, tokens, passwords, or provider-specific credentials. Configure provider environment variables in the client or process environment. Runtime and upstream failures remain subject to the existing MCP sanitization and source-only boundaries.

## Distribution boundary

Agent Plugins 1.0 defines a portable package format; it is not a central marketplace. Client-specific discovery and distribution remain the responsibility of each client. Glama and other MCP directories are separate ingestion surfaces and are not required for the package release.

## Verification scope

The release candidate is verified with the full package test suite, Ruff, compilation, lock/build checks, canonical Agent Plugins schema validation, Sdist/Wheel inspection, exact `mcp.json` `uvx` startup, MCP `initialize`, and `tools/list` without provider requests.
