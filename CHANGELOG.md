# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
