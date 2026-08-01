# web-search-plus-mcp 3.5.0 release notes

`web-search-plus-mcp 3.5.0` moves the low-level stdio boundary to MCP Python SDK v2 while preserving the stable `web_search` and `web_extract` tool surface.

## Highlights

- Require the MCP Python SDK v2 line (`mcp>=2.0.0,<3`) and the SDK-v2 HTTP client line (`httpx2>=2.5.0`).
- Negotiate the stateless MCP `2026-07-28` protocol for modern clients while retaining the `2025-11-25` legacy handshake path.
- Validate tool arguments at the SDK boundary and return sanitized typed failures for unknown tools, invalid arguments, and unexpected execution errors.
- Port the optional Hound loopback sidecar bridge to the SDK-v2 two-stream transport, float timeouts, and snake_case result fields.
- Keep the package stdio-only. Streamable HTTP session removal, subscriptions, OAuth changes, tasks, and multi-round-trip requests are outside this release's public surface.

## Compatibility and upgrade

- Python `>=3.10` remains supported.
- The public MCP tool names and documented arguments remain `web_search` and `web_extract`.
- Clients that still initiate the `2025-11-25` handshake can continue to connect over stdio; modern clients negotiate `2026-07-28`.
- Upgrade with:

  ```bash
  pip install --upgrade "web-search-plus-mcp==3.5.0"
  ```

- If you use Hound, keep `HOUND_MCP_URL` pointed at an uncredentialed loopback endpoint of the form `http://127.0.0.1:<port>/mcp` or `http://[::1]:<port>/mcp`. The adapter refuses redirects, credentials, query strings, fragments, non-loopback hosts, and non-`/mcp` paths.

## Security boundary

The server does not collect or provide provider credentials. Provider secrets remain in the host environment, and Hound remains an explicit-only local sidecar integration. Runtime and upstream failures are sanitized before they cross the MCP boundary.

## Verification scope

The release candidate includes unit, contract, protocol-negotiation, real subprocess stdio, provider, compilation, lockfile, lint, and packaging checks. The final release report records the exact executed test and artifact results.
