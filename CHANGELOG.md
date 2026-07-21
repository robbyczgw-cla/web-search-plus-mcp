# Changelog

## [1.1.1] - 2026-07-21

### Fixed
- The MCP `web_extract` projection now preserves `spans` and `span_contract_version` on result items; previously the engine computed spans but clients never received them.
- `wsp_sdk` imports as a plain package again (its `ProviderRequestError` import no longer depends on test-only `sys.path` layout).
- Extraction requests served by discovered Provider-SDK extraction providers no longer fail closed inside the cache identity; SDK providers contribute a deterministic identity derived from their spec and the non-secret scalar settings of their config section. Unknown providers still fail closed.
- The `providers.d` non-production gate acts before module execution: modules declaring a literal `production=False` are skipped without being imported unless `WSP_SDK_ALLOW_NON_PRODUCTION` is set.

## [1.1.0] - 2026-07-20

### Added
- Sync the portable Web Search Plus v3.1.1 policy layer: budget preflight, diversity scoring/reranking, self-hosted profiles, shadow-policy observations, semantic extraction spans, extraction cache identity v6, and SQLite state schema v3.
- Add the public `wsp_sdk` package plus fail-closed `providers.d` discovery, startup diagnostics, and network-free provider conformance checks.
- Expose deterministic semantic spans through the MCP `web_extract` schema and CLI projection.

### Changed
- Generate and ship the current v3 request/response schemas, including budget-preflight receipts and span options.
- Keep MCP-specific stdio, subprocess, tool names, legacy projections, and auto-fallback behavior authoritative while syncing the portable engine to Web Search Plus v3.1.1.

### No-port scope
- Hermes plugin loading, Operator Console, receipt journals, benchmark/release tooling, and Hermes runtime hooks remain intentionally outside the standalone MCP package.

### Verification
- 265 tests pass, including 73 portable v3.1 feature tests and provider-SDK discovery/conformance subprocess coverage.

## [1.0.1] - 2026-07-20

### Fixed
- Restore multi-provider fallback expansion for normal `provider=auto` Search and Extract requests across the MCP → CLI → v3 projection boundary. The CLI's absent `--allow-fallback` flag no longer serializes an explicit `allow_fallback: false` that collapses auto plans to one candidate.
- Keep explicit provider requests strict by default; they fall back only when `--allow-fallback` is explicitly requested.

### Verification
- Add issue #27 regressions proving multi-candidate auto plans and an executed second-provider fallback after a simulated `429` for both Search and Extract.
- Full suite: 187 tests passing locally and on Python 3.10, 3.11, and 3.12 in CI.

## [1.0.0] - 2026-07-14

### Breaking
- Align the standalone MCP server with Web Search Plus 3.0's mechanically source-only contract. Native Perplexity and Kilo Perplexity answer endpoints are removed from public provider schemas because they do not expose a verified source-only mode; direct low-level calls fail closed with the typed `wsp.provider.source_only_required` error before provider dispatch.
- Reduce the public search surface from 14 mixed providers to 12 source-result providers. The extraction surface remains 8 providers.

### Added
- Port the Web Search Plus v3 request/response contracts, lossless source observations, provider-attempt and routing receipts, typed errors, cache-origin evidence, deterministic compatibility projections, and generated v3 JSON Schemas.
- Port bounded extraction context with a 10-URL call limit, deterministic inline truncation, local full-text storage, and page-on-demand references.
- Port marker-owned v3 cache/state storage, dry-run/backup/rollback migration primitives, provider adapter validation, guarded request gates, and source-independence metadata.
- Add `web-search-plus-mcp config set-auto-allow <provider> on|off` for explicit guarded-provider participation in auto-routing.
- Add a 0.x-to-1.0 migration guide covering retired providers, additive response fields, MCP host schema refresh, and rollback.

### Changed
- Keep the two stable MCP tools, `web_search` and `web_extract`, while routing both through the canonical `--contract-v3` engine path and projecting v3 responses additively onto the established MCP result shape.
- Keep Classic Routing v2 authoritative, promote Brave into the default auto-pool for independent-index diversity, and preserve deterministic source-only fallback behavior.
- Update package, server, User-Agent, README, Glama, lockfile, and build metadata to `1.0.0`, aligned with the Web Search Plus v3.0.2 engine family.

### Fixed
- Sync the portable Web Search Plus v3.0.2 entrypoint repairs: bounded Research Mode fan-out, immutable timeout/cancellation snapshots, honest provider-attempt evidence, and consistent cache keys across request options.
- Preserve extracted body text, immutable full-text references, global context bounds, cache provenance, and miss-to-hit semantics across the canonical v3 pipeline.
- Keep the MCP legacy projection's aggregate provider identity as `research` while preserving canonical multi-provider attempts, observations, and receipts additively.
- Advertise the MCP package version in the `initialize` handshake instead of leaking the installed MCP SDK version as the server version.
- Give Research Mode subprocesses a fixed grace window beyond the requested inner budget and convert outer timeouts into sanitized, retryable `wsp.subprocess.timeout` responses.

### Security
- Preserve private/internal extraction-target blocking, credential-free public manifest data, typed provider failures, and fail-closed rejection of answer-only provider modes.
- Convert malformed subprocess stdout/stderr into controlled typed protocol errors without exposing raw diagnostics, while retaining the additive legacy `error` string.

### MCP-specific scope
- Keep the standalone stdio/subprocess boundary. The Hermes plugin's in-process lazy loader, Operator Console, setup helpers, and v3.0.1 import-precedence hotfix are intentionally not ported because they do not apply to a normal installed MCP package.

### Tests
- Add contract, provider-surface, bounded-context, source-only rejection, compatibility-projection, schema, documentation, and Glama drift gates.
- Port the Web Search Plus 3.0 state-migration and SQLite-state suites: dry-run/apply/no-op/rollback, backup integrity, tamper and symlink rejection, WAL initialization, circuit isolation, and atomic concurrent budget reservation.
- Port the portable v3.0.2 entrypoint regressions and add MCP-boundary coverage for Research Mode identity and extract cache-hit body/provenance preservation.
- Add GitHub Actions coverage for Python 3.10, 3.11, and 3.12 plus Ruff, compile, wheel, and source-distribution builds.

### Attribution
- Synced from upstream Web Search Plus PRs [#104](https://github.com/robbyczgw-cla/hermes-web-search-plus/pull/104) and [#105](https://github.com/robbyczgw-cla/hermes-web-search-plus/pull/105) by [@robbyczgw-cla](https://github.com/robbyczgw-cla).

## [0.17.0] - 2026-07-10

### Security
- Sync the Web Search Plus v2.9.1 cache-ownership fix: cache stats and clear now recognize only complete WSP search-cache envelopes, preserving `provider_stats.json`, `provider_health.json`, host-written usage state, unrelated/corrupt JSON, and invalid UTF-8 files byte-for-byte.

### Added
- Add independent `auto_routing.extract_provider_priority` configuration for `web_extract(provider="auto")`, including `web-search-plus-mcp config set-extract-priority ...` and status/config output. Partial lists append missing extract-capable providers in registry order; search priority remains independent. Synced from upstream #89 by @robbyczgw-cla.

### Changed
- Raise Parallel extraction's default full-content budget from 6k to 60k characters per result and from 12k to 120k total, while preserving explicit config overrides. Synced from upstream #86 by @robbyczgw-cla.
- Bump package, server, User-Agent, lockfile, README, and build metadata to `0.17.0`, aligned with Web Search Plus v2.9.1 plus the post-release extract-priority feature.

### Attribution / no-port notes
- Upstream v2.9.1 release PR #88 by @robbyczgw-cla supplied the cache-safety maintenance and release inventory. Hermes-only release tooling/version surfaces remain intentionally outside the MCP package.

## [0.16.0] - 2026-07-03

### Synced from Web Search Plus v2.9.0
- Port registry-aligned provider dispatch updates from upstream PR #79 where applicable to MCP.
- Add Serper webpage scraper extraction support and include Serper in MCP extraction provider schema/fallback order (upstream PR #80).
- Add Serper news/search_type and configurable locale defaults/query-aware locale resolution to the MCP search surface (upstream PR #80/#81).
- Bump MCP package/server/User-Agent surfaces to v0.16.0 and align upstream Web Search Plus User-Agent baseline with v2.9.0 (upstream PR #82).
- Refresh README/API docs for Serper extraction capability (upstream PR #84).

### Attribution / no-port notes
- Upstream PR #77 golden snapshot recorder is test/eval infrastructure and is credited but not ported wholesale.
- Upstream PR #83 prepare_release.py is repository-specific release automation; MCP keeps its own version surfaces for now.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.15.0] - 2026-07-02

### Security
- Sync Web Search Plus v2.8.1 authority-domain matcher hardening from upstream #68: canonical boosts now apply only to exact domains, true subdomains, or explicit label-prefix rules, blocking look-alike domains such as `nih.gov.evil.example` from inheriting trust.
- Sync Web Search Plus v2.8.x HTTP provider hardening: corrupted gzip/deflate bodies, non-UTF-8 responses, invalid JSON, read interruptions, `socket.timeout`, and `Retry-After` on HTTP 429 are normalized into structured provider errors.

### Added
- Add MCP-specific extract preview/store handling for oversized extraction results. Large `content`, `markdown`, `text`, or `raw_content` fields are bounded in MCP responses and full text is stored under the local cache with `stored_extract` metadata.

### Fixed
- Derive `DEFAULT_USER_AGENT` from the package `__version__` so MCP releases cannot drift again; v0.14.0 still advertised `ClawdBot-WebSearchPlus-MCP/0.13.0`.

### Changed
- Bump package/server version to `0.15.0` and align README/changelog with the Web Search Plus v2.8.1 engine family where applicable.
- Keep upstream #72 provider bench and #75 Hermes standalone-plugin import fix out of MCP by design: bench is CLI/provider-quota-sensitive and #75 does not apply to a normal installed MCP package.
- Leave existing MCP `time_range` search plumbing behavior-preserving; upstream #71 freshness unification is not treated as a breaking schema rewrite in this release.

### Tests
- Add regression coverage for authority look-alike rejection, HTTP hardening and User-Agent version drift, and oversized extract store/preview behavior.

## [0.14.0] - 2026-06-30

### Security
- Sync Web Search Plus v2.7.0 private/internal extraction target guard from upstream #61: `web_extract` now blocks loopback, RFC1918, CGNAT/shared-address ranges, IPv6 ULA/link-local/mapped-private addresses, multicast, cloud metadata hosts, and hostnames resolving to private/internal IPs before provider dispatch. Operator-configured provider endpoints (for example local Firecrawl-compatible backends) remain allowed; trusted intranet extraction requires explicit `extract.allow_private_urls: true`.

### Fixed
- Sync upstream #63 behavior: provider configuration errors such as missing API keys no longer mark providers unhealthy or place them into cooldown.

### Changed
- Bump package/server version to `0.14.0` and align README/changelog with the Web Search Plus v2.7.0 engine family where applicable.

### Notes
- Upstream #60 by @IlyaGusev added keyless-provider setup wizard and config rewrite preservation to the Hermes plugin. MCP already has its own onboarding/config surface and Keenable keyless semantics from v0.13.0, so no setup-wizard code was ported; attribution is carried forward for the synced release window.
- Upstream #62 added `setup.py fastpath`, a public-Hermes diagnostic. That command is Hermes-plugin-specific and not applicable to the standalone MCP package.
- Upstream #59 README hero/Querit URL cleanup and #64 release-prep changes are credited as release-window context; only MCP-relevant docs/version metadata changed here.

### Tests
- Add extract target safety coverage for private IPv4/IPv6 ranges, CGNAT/Tailscale-style addresses, cloud metadata, DNS rebinding/mixed DNS answers, explicit private-URL escape hatch, and local provider endpoint preservation.
- Add regression coverage that explicit missing-key search failures do not call provider-health cooldown marking.

## [0.13.0] - 2026-06-26

### Added
- Sync Keenable provider support from Web Search Plus v2.6.0: `keenable` search and extraction via `KEENABLE_API_KEY`, plus an opt-in keyless public tier that is off by default. Thanks @IlyaGusev for WSP #56.
- Document GroktoCrawl / local Firecrawl-compatible backend usage through existing Firecrawl `api_url` and `scrape_url` overrides, with regression tests for custom endpoints. (#57)

### Changed
- Bump package/server version to `0.13.0` and align README, schemas, provider counts, and User-Agent with the Web Search Plus v2.6.1 engine family.
- Add Keenable to generated provider metadata, MCP provider enums, auto-routing priority tail, and extraction fallback tail.

### Notes
- Upstream Web Search Plus v2.6.0 also included an in-process Hermes-plugin loader fix (#55 by @maksym-mishchenko). That loader path is not applicable to the standalone MCP server, so no code was ported; it is noted here for release-history completeness.

### Tests
- Add Keenable key/keyless configuration, search, extraction, public-warning, schema, and Firecrawl-compatible endpoint override tests.

## [0.12.0] - 2026-06-16

### Fixed
- `extract_plus` now respects `disabled_providers` from `config.json`. Previously only search routing honored the disabled-provider list; extraction used a hardcoded provider order, causing disabled providers to still be called during URL extraction. Explicit provider selection still tries the requested provider first, matching search semantics.

### Changed
- Bump package/server version to `0.12.0` and align metadata/User-Agent with the Web Search Plus v2.5.1 engine family.
- Update README version note to track v2.5 engine family.

### Tests
- Add tests covering auto-mode extraction skip and explicit-provider fallback behavior when providers are disabled in config.

## [0.11.0] - 2026-06-08

### Added
- Sync Web Search Plus v2.4 engine improvements: bounded random retry-backoff jitter (`RETRY_JITTER_FRACTION`) so concurrent or repeated retries against a recovering provider no longer synchronize into bursts.
- Guard provider-health read-modify-write with a process lock (`_HEALTH_LOCK`) so concurrent in-process provider calls (parallel research mode) cannot lose cooldown updates.
- Research mode now queries its providers concurrently via a thread pool instead of sequentially, so wall-clock cost tracks the slowest provider rather than the sum of all of them. Result ordering stays deterministic (preserved by provider submission order) and the time budget still gates which providers launch and whether extraction runs.

### Changed
- Bump package/server version to `0.11.0` and align metadata/User-Agent with the Web Search Plus v2.4 engine family.

### Notes
- Hermes-plugin-only changes from v2.4.0 (in-process search/extract entry points, `~/.hermes/.env` profile loading via `env_loader`) are intentionally not synced: the MCP package runs `search.py` as a subprocess and ships its own standalone `.env` loading and onboarding surface.

## [0.10.0] - 2026-05-29

### Added
- Sync Web Search Plus v2.3 provider registry into the MCP package so provider metadata, schemas, defaults, guarded auto-routing, and capability labels share one source of truth.
- Add provider health/doctor, cache, retry, quality, routing, search, and extraction parity updates from the v2.3 engine family.

### Changed
- Generate MCP provider enums and server metadata from the shared registry instead of hand-maintained static lists.
- Align provider ordering, auto-routing behavior, and guarded explicit-only providers with Web Search Plus v2.3.
- Bump package/server version to `0.10.0`.

### Tests
- Add/refresh regression coverage for registry-derived schemas, SerpBase/guarded auto-allow behavior, Parallel metadata, HTTP content encoding, and compatibility shims.
- Release validation includes compileall, Ruff, 44 pytest tests, wheel build, clean-venv install, MCP stdio handshake/list-tools, doctor, no-key error path, and live search/extract smoke tests.

## [0.9.0] - 2026-05-19

### Added
- Sync Parallel provider support from Web Search Plus v2.2: explicit `parallel` search/extract support via `PARALLEL_API_KEY`.
- Add Parallel to extraction auto fallback order: Tavily → Exa → Linkup → Parallel → Firecrawl → You.com.

### Changed
- Keep Parallel guarded from automatic routing by default with `auto_allow=false`; direct `provider="parallel"` calls still work.
- Preserve user routing priority order while appending newly introduced default providers during config normalization.

### Tests
- Add regression coverage for Parallel search normalization, extraction normalization, explicit-only routing, MCP schemas, and provider metadata.

## [0.8.0] - 2026-05-16

### Changed
- Sync MCP surface with Web Search Plus v2.1: remove the beta `web_answer` tool and keep the stable MCP surface to `web_search` + `web_extract`.
- Switch extraction auto fallback order to Tavily → Exa → Linkup → Parallel → Firecrawl → You.com based on the v2.1 extraction benchmark.
- Update package metadata, README, and Glama manifest for the v2.1 engine family.

### Migration
- Remove `WSP_ENABLE_WEB_ANSWER`; it is ignored because `web_answer` is no longer exposed. Use `web_search` for source discovery and synthesize in the MCP host.

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
