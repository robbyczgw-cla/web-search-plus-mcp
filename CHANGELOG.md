# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-05-15

### Added
- Sync Routing v2 from Web Search Plus v2.0.0: class-aware query routing, multilingual/current detection, answer-mode recommendations, and `routing_policy` diagnostics.
- Add regression tests for guarded defaults, legacy `auto_allow` migration, multilingual routing, arXiv/docs/security classes, and answer/synthesis hints.

### Changed
- Update the default auto-routing pool to You.com, Serper, Exa, Firecrawl, Tavily, and Linkup.
- Keep Brave, SerpBase, Querit, native Perplexity, and Kilo Perplexity explicit-only by default with `auto_allow=false`.
- Update MCP presets so `starter` uses You.com + Serper + Linkup, `lean` uses You.com + Linkup, and `minimal` uses You.com.

### Migration
- Existing config files are still valid. Missing `auto_allow` entries inherit the new guarded defaults while explicit user overrides remain intact.
- Explicit provider calls still work for guarded providers; `auto_allow=false` only blocks automatic `provider="auto"` selection.

## [0.6.0] - 2026-05-15

### Added
- Sync SerpBase provider support from Hermes Web Search Plus v1.10.0, including explicit `serpbase` selection, `SERPBASE_API_KEY`, and SerpBase result normalization.

### Changed
- Add `auto_allow` routing gates so SerpBase and Querit stay explicit-only by default while remaining available for direct provider calls.
- List explicit-only SerpBase and Querit last in general provider docs and MCP schemas.
- Align MCP package with the Web Search Plus v1.10.x engine family.

### Tests
- Add regression coverage for explicit-only auto-routing gates, direct SerpBase calls, MCP schema ordering, and server auto-allow metadata.

## [0.5.1] - 2026-05-14

### Fixed
- Split native `perplexity` from `kilo-perplexity` so direct Perplexity uses `PERPLEXITY_API_KEY`, `https://api.perplexity.ai/chat/completions`, and `sonar-pro`.
- Keep Kilo gateway routing under the distinct `kilo-perplexity` provider using `KILOCODE_API_KEY`, `https://api.kilo.ai/api/gateway/chat/completions`, and `perplexity/sonar-pro`.
- Normalize `kilo_perplexity` to `kilo-perplexity` without aliasing it to native `perplexity`.

### Migration
- Existing Kilo gateway users who previously selected `perplexity` with only `KILOCODE_API_KEY` should switch explicit provider config to `kilo-perplexity` or set a native `PERPLEXITY_API_KEY`.

### Docs
- Add Web Search Plus logo assets used by the README and directory listings.

### Tests
- Add regression coverage for provider defaults, env-key lookup, missing-key errors, aliases, auto-routing preference, cache separation, and MCP server metadata.

### Contributors
- Robby Czesany / robbyczgw-cla

## [0.5.0] - 2026-05-09

### Added
- Add persistent routing preference CLI: `config show`, `set-default`, `set-routing`, `set-priority`, `set-fallback`, `disable`/`enable`, `set-threshold`, and `reset --yes`.
- Add `WEB_SEARCH_PLUS_CONFIG` and `--config-path` support for isolated MCP host installs.
- Add routing preference fields to `status --json` without exposing provider secrets.

### Changed
- Align MCP package with the Web Search Plus v1.9.x engine family.
- Make fixed-provider mode strict when auto-routing is disabled: `provider="auto"` uses only the configured default provider.
- Validate and quarantine malformed or semantically invalid config files at runtime.

### Tests
- Add coverage for config commands, alias normalization, strict fixed-provider routing, and invalid config quarantine.

## [0.4.0] - 2026-05-09

### Added
- Add optional beta `web_answer` MCP tool for source-backed cited briefs.
- Gate `web_answer` behind `WSP_ENABLE_WEB_ANSWER=1` so the default tool surface stays stable and small.
- Add MCP-native onboarding CLI: `status`, `list providers`, `list presets`, and `setup`.
- Add setup presets: `minimal`, `lean`, `starter`, and `all`.
- Add tests for beta tool gating, answer command mapping, and onboarding dry-run/status behavior.

### Changed
- Bump MCP package to `0.4.0` and align docs with the Web Search Plus v1.8.x engine family.
- Keep `web_search` as the recommended default for source discovery, current events, prices, weather, sports lineups, and schedules.
- Set `web_answer` freshness default to `none` to avoid over-triggering recency filters.
- Update the console entrypoint so `web-search-plus-mcp` runs the server by default but also supports onboarding subcommands.
- Prefer Linkup first in extraction provider docs/metadata.

### Notes
- `web_answer` is intentionally beta. Promote only after real MCP host dogfooding shows the contract is stable.
- Hermes plugin users know this capability as `web_answer_plus`; the MCP-native tool name is `web_answer`.
- Locale/language expansion and Routing v2 remain out of scope for this release.

## [0.2.1] - 2026-05-07

### Fixed
- Fix Brave Search failures when urllib receives gzip-compressed API responses.
- Add shared compressed-response handling for normal and HTTP error bodies.
- Add regression coverage for gzip/deflate response decoding.

## [0.2.0] - 2026-05-03

### Added
- Sync MCP server with the Web Search Plus v1.7 Python engine
- Add `web_extract` MCP tool with Linkup, Firecrawl, Tavily, Exa, and You.com extraction providers
- Add 10-provider search schema: Serper, Brave, Tavily, Exa, Querit, Linkup, Firecrawl, Perplexity, You.com, SearXNG
- Expose `depth`, `time_range`, domain filters, `quality_report`, opt-in `research` mode, and `research_time_budget`

### Changed
- Update README and package metadata for search + extraction MCP usage

## [0.1.2] - 2026-03-14

### Fixed
- Entry point now correctly wraps async `main()` with `asyncio.run()` via a `run()` function
- Fixes `coroutine 'main' was never awaited` error when running via `uvx`, `pip install`, or Docker
- Previously only worked when invoked directly as `__main__`; now works in all environments

## [0.1.1] - 2026-03-13

### Added
- Dockerfile for containerized deployment
- `glama.json` metadata for Glama MCP directory listing
- Support for all 7 search providers: Serper, Tavily, Exa, Perplexity, You.com, SearXNG, Querit
- Intelligent auto-routing based on query intent

### Changed
- Improved README with installation and configuration instructions

## [0.1.0] - 2026-03-13

### Added
- Initial release
- MCP server with `web_search` tool
- Auto-routing between Serper (facts/news), Tavily (research), and Exa (discovery)
- Support for `uvx web-search-plus-mcp` installation
- Environment variable configuration for API keys
