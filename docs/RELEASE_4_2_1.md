# Web Search Plus MCP 4.2.1

Same public version as Hermes Web Search Plus 4.2.1. MCP tool names, arguments, and legacy result fields stay the same.

## Cache freshness

`web_search` now accepts `no_cache` and `cache_ttl`, matching the CLI flags. Clients can bypass or shorten the search cache without a server restart.

## DonSeTch 4.2.9

The optional local adapter now treats **4.2.9** as the tested DonSeTch version. Other parsed versions, including 3.x, are `compatible_unverified`. A different major is not treated as broken. DonSeTch stays a separately installed upstream project ([dondai44423/donsetch](https://github.com/dondai44423/donsetch), AGPL-3.0-only) and is not bundled.

## Upgrade

Pin `web-search-plus-mcp==4.2.1` in `uvx` and Agent Plugins manifests.

```bash
uvx --from web-search-plus-mcp==4.2.1 web-search-plus-mcp status
```

The opt-in Hermes native `wsp` backend remains Hermes-plugin-only. Optional Jev stays off by default; see the [4.2.0 notes](RELEASE_4_2_0.md).
