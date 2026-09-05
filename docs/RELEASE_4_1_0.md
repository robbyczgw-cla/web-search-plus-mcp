# Web Search Plus MCP 4.1.0

Version-line alignment with Hermes Web Search Plus 4.1.0. Stable MCP tool names, arguments, and legacy result fields stay the same.

## DonSeTch 3.6.1

- Read search titles and snippets from compact text evidence, matched to the original result rank and URL or handle before domain filtering.
- Recover search diagnostics and fetch title, status, quality, and site from DonSeTch namespaced metadata. Do not expose the raw debug envelope.
- Continue accepting pre-compact structured responses.
- Pin the child transport to stdio even when the parent environment requests HTTP; leave the parent environment unchanged.

DonSeTch remains a separately installed optional provider ([dondai44423/donsetch](https://github.com/dondai44423/donsetch), AGPL-3.0-only). Search and extraction stay source-only. No automatic backend selection is introduced.

## Hermes-only native backend (not in this package)

Hermes Web Search Plus 4.1.0 adds an opt-in `wsp` native backend so Hermes `web_search` and `web_extract` can call the in-process WSP engine. That adapter lives only in the Hermes plugin. This MCP package does not ship, port, or register a native Hermes `WebSearchProvider`.

MCP clients continue to use the existing MCP tools `web_search` and `web_extract` through stdio or their host configuration. No new MCP tool, backend name, or Hermes plugin registration is required here.

The Hermes-only enhancement follows the integration direction raised by [@LugMuad](https://github.com/LugMuad) in [hermes-web-search-plus#125](https://github.com/robbyczgw-cla/hermes-web-search-plus/issues/125). The shipped Hermes implementation is an in-process bridge rather than a separate CLI wrapper plugin.

## What did not change

- Source-only search and extract contracts
- Provider registry size and explicit-only defaults for DonSeTch
- Agent Plugins manifests and the exact `uvx` version pin pattern (now `4.1.0`)
