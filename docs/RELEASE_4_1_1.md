# Web Search Plus MCP 4.1.1

Adapter fidelity with Hermes Web Search Plus 4.1.1. MCP tool names, arguments, and legacy result fields stay the same.

## What changed

- Exa search prefers requested `highlights` over the first 800 characters of page text when both exist.
- Parallel Search sends `max_results` and domain filters in `advanced_settings.source_policy` instead of stuffing `site:` into the query.
- Tavily Search forwards the unified `freshness` / `time_range` filter as native `time_range`. Result metadata reports `freshness.applied=true` when that happens.

The opt-in Hermes native `wsp` backend remains Hermes-plugin-only. This package does not ship it. DonSeTch stays a separately installed upstream project.

## Upgrade

Pin `web-search-plus-mcp==4.1.1` in `uvx` and Agent Plugins manifests.
