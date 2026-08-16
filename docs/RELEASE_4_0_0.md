# web-search-plus-mcp 4.0.0 release notes

`web-search-plus-mcp 4.0.0` replaces the optional Hound provider with a
separately installed DonSeTch 2.1.0 stdio provider. The public MCP tool names
remain source-only and unchanged.

## Removed

- Remove the Hound provider and `HOUND_MCP_URL` configuration.
- Remove the Hound Streamable HTTP adapter and Hound-specific setup guidance.

## Added

- Add DonSeTch 2.1.0 as an explicit-only local Search/Fetch provider.
- Configure the external DonSeTch executable through `DONSETCH_BIN`.
- Normalize DonSeTch `initialize`, `web_search`, `web_fetch`, and structured
  error responses into the existing Web Search Plus envelopes.
- Keep DonSeTch outside the package distribution; it is an independent
  AGPL-3.0-only component that operators install separately.

## Upgrade

1. Remove `HOUND_MCP_URL` from MCP host configuration.
2. Install DonSeTch 2.1.0 separately.
3. Set `DONSETCH_BIN` to its absolute executable path.
4. Change explicit `provider="hound"` requests to `provider="donsetch"`.
5. Keep the provider explicit-only until its behavior is verified on the target
   host. Automatic routing remains an operator choice.

## Verification boundary

The adapter was exercised against DonSeTch 2.1.0 for stdio initialization,
Search, Fetch, and structured error handling. The standalone MCP wrapper gives
explicit DonSeTch calls a 195-second outer subprocess budget, covering the
adapter's 180-second inner timeout. Browser and anti-bot outcomes are
environment-dependent and are not guaranteed by this package.

See [DonSeTch.md](DONSETCH.md) for setup, licensing, migration, and security
boundaries.
