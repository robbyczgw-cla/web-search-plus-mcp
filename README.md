# 🔍 web-search-plus-mcp

<p align="center">
  <img src="https://raw.githubusercontent.com/badlogic/web-search-plus-mcp/main/docs/assets/web-search-plus-logo.png" alt="Web Search Plus" width="180">
</p>

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![CI](https://github.com/robbyczgw-cla/web-search-plus-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/robbyczgw-cla/web-search-plus-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Glama](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp/badge)](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp)

**Source-only multi-provider web search and bounded URL extraction for MCP clients.**

`web-search-plus-mcp` is the standalone MCP packaging of Web Search Plus. It gives Claude Desktop, Cursor, NanoBot, Hermes native MCP, and other MCP-compatible hosts the source-only provider and evidence contract of Web Search Plus 3.0 without depending on the Hermes plugin runtime.

Version note: `web-search-plus-mcp` uses its own MCP package version (`1.0.0`) while tracking the source-only Web Search Plus v3.0.2 engine. The Hermes plugin is versioned separately; its plugin-loader, setup, Console, and release commands are not exposed by the standalone MCP server.

## ✨ Features

- **12 search providers + auto-routing** — source-result providers only; answer-only endpoints are rejected instead of being presented as search
- **8 extract providers with private-target protection** — Tavily, Exa, Linkup, Parallel, Firecrawl, You.com, Keenable, Serper
- **Additive v3 evidence contract** — source observations, provider attempts, routing receipts, cache provenance, typed errors, and deterministic legacy projections
- **Bounded extraction context** — long pages return a bounded preview plus a page-on-demand reference to the stored full text
- **Classic Routing v2 authority** — registry-backed routing for multilingual/current, docs/API, arXiv, CVE/security, local/shopping, and OSS discovery
- **Quality reports + doctor checks** — optional routing/result diagnostics plus compact offline health checks for configured providers/cache
- **Research mode** — opt-in multi-provider search + top-source extraction with a time budget
- **Onboarding CLI** — `status`, `list`, `setup`, and persistent routing `config` helpers for MCP env/config wiring
- **Zero-install run** — `uvx web-search-plus-mcp`
- **MCP-native** — stdio server exposing stable `web_search` and `web_extract` tools

## What changes in 1.0

- Native Perplexity and Kilo Perplexity answer endpoints are removed from the public provider enums because they do not expose a verified source-only mode.
- The two MCP tool names and their legacy result fields remain stable. v3 evidence, attempts, receipts, limits, stored-content references, warnings, and typed errors are additive.
- Existing config entries for retired answer providers are ignored in provider lists; retired default/fallback values are replaced in memory with `serper` and reported as a migration warning.
- The MCP server keeps its stdio/subprocess boundary. Hermes-specific in-process plugin loading and Operator Console surfaces are intentionally not ported.

See [Migrating to 1.0](docs/MIGRATION_1_0.md) before upgrading an existing 0.x installation.

## 🚀 Quick Start

```bash
# Run the MCP server instantly with uvx
uvx web-search-plus-mcp

# Or install globally
pip install web-search-plus-mcp
web-search-plus-mcp
```

At least one provider credential is required for search. Extraction needs at least one extraction-capable provider key.

## 🧭 Easier onboarding

Check configured providers:

```bash
web-search-plus-mcp status
```

List providers or presets:

```bash
web-search-plus-mcp list providers
web-search-plus-mcp list presets
```

Write a starter `.env` template and print a canonical MCP stdio snippet:

```bash
web-search-plus-mcp setup --preset starter
```

The recommended starter preset is **You.com + Serper + Linkup**. It gives a practical source-only baseline for fast current search, Google-style discovery, and extraction workflows without wiring every provider on day one.


`status` returns a non-zero exit code when no search provider is configured, which makes it usable as a config check in scripts.

Persistent routing preferences live in `config.json` rather than `.env`:

```bash
web-search-plus-mcp config show
web-search-plus-mcp config set-default you        # strict fixed-provider mode
web-search-plus-mcp config set-routing on         # restore auto-routing
web-search-plus-mcp config set-priority you,serper,exa,firecrawl,tavily,linkup,parallel,brave,keenable
web-search-plus-mcp config set-extract-priority serper,tavily,exa,linkup,parallel,firecrawl,you,keenable
web-search-plus-mcp config set-fallback serper
web-search-plus-mcp config disable parallel
web-search-plus-mcp config enable parallel
web-search-plus-mcp config set-auto-allow parallel on
web-search-plus-mcp config set-threshold 0.45
web-search-plus-mcp config reset --yes
```

Use `--config-path /path/to/config.json` or `WEB_SEARCH_PLUS_CONFIG=/path/to/config.json` for isolated MCP host installs. Provider secrets stay in environment variables; routing behavior stays in `config.json`. Search and extraction priorities are independent. If an extraction priority lists only selected providers, the remaining extract-capable providers are appended in the public registry order.

Other presets:

- `minimal` — You.com only
- `lean` — You.com + Linkup
- `starter` — You.com + Serper + Linkup
- `all` — every supported provider env var

## ⚙️ MCP host config

Canonical stdio snippet for Claude Desktop, Cursor, NanoBot, or Hermes native MCP:

```json
{
  "mcpServers": {
    "web-search-plus": {
      "command": "uvx",
      "args": ["web-search-plus-mcp"],
      "env": {
        "YOU_API_KEY": "your_you_key",
        "SERPER_API_KEY": "your_serper_key",
        "LINKUP_API_KEY": "your_linkup_key"
      }
    }
  }
}
```

Common places to paste this snippet:

- Claude Desktop macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Claude Desktop Windows: `%APPDATA%\\Claude\\claude_desktop_config.json`
- Claude Desktop Linux: `~/.config/Claude/claude_desktop_config.json`
- Cursor: project/user MCP config using the same `mcpServers` shape
- Hermes native MCP: `~/.hermes/config.yaml` under `mcp_servers` with equivalent command/env fields

You can also place a `.env` file next to the package/project with the same variables.

## 🔎 Search Providers

- **You.com** — fast source-result provider for current and multilingual search
- **Serper** — Google-style facts, news, shopping, local queries
- **Exa** — semantic discovery, GitHub/docs, arXiv/academic, and OSS discovery
- **Firecrawl** — web search plus scrape-ready content
- **Parallel** — explicit-only LLM-ready web search with long excerpts (`PARALLEL_API_KEY`, `auto_allow=false`)
- **Tavily** — research and analysis
- **Linkup** — source-backed grounding/citations
- **Brave** — explicit-only independent web index by default (`BRAVE_API_KEY`, `auto_allow=false`)
- **SearXNG** — privacy-first self-hosted meta-search
- **SerpBase** — explicit-only Google SERP API (`SERPBASE_API_KEY`, `auto_allow=false`)
- **Querit** — explicit-only multilingual, real-time AI search (`QUERIT_API_KEY`, `auto_allow=false`)
- **Keenable** — independent web index with search and extraction (`KEENABLE_API_KEY`, or opt-in keyless public tier; off by default)

## 📄 Extract Providers

- **Tavily** — public default first choice; fastest reliable extraction in the v2.1 benchmark
- **Exa** — fast contents API, strong for docs/academic pages
- **Linkup** — clean markdown and source-grounded fetches
- **Parallel** — docs-focused fallback with full-content defaults of 60k characters per result / 120k total
- **Firecrawl** — robust scrape fallback, useful for JS-heavy/blocked pages
- **You.com** — LLM-ready snippets/content where available
- **Keenable** — keyed or explicitly opted-in public extraction
- **Serper** — fast webpage scraper extraction

`auto_routing.extract_provider_priority` can override the auto-extraction order without changing search routing. Explicit provider calls still try the requested provider first.

### Keenable keyless public access

Keenable exposes authenticated endpoints via `KEENABLE_API_KEY`. It also has keyless `/public` endpoints, but those are **opt-in and disabled by default**. Without a key, Keenable is treated as unconfigured unless you explicitly enable public egress:

```json
{ "keenable": { "allow_public": true } }
```

or set:

```bash
KEENABLE_ALLOW_PUBLIC=1
```

Use an API key for private or production use. The public endpoint sends queries and fetched URLs to a shared unauthenticated service and remains near the tail of the public default fallback order unless the operator configures a different extraction priority.

### Private/internal extraction target guard

`web_extract` blocks user-supplied target URLs that point at private or internal networks before any provider is called. This covers loopback, RFC1918, CGNAT/shared-address ranges, IPv6 local/mapped-private ranges, multicast, cloud metadata hosts, and hostnames resolving to private/internal IPs.

Operator-configured provider endpoints are separate: local Firecrawl-compatible backends can still run on `127.0.0.1` through provider config. If you intentionally need to extract trusted intranet URLs, opt in explicitly:

```json
{ "extract": { "allow_private_urls": true } }
```

Leave this off for public/agent-controlled URL extraction.

### GroktoCrawl / local Firecrawl-compatible backends

The Firecrawl provider can target a local Firecrawl-v2-compatible backend by overriding its search and scrape URLs in `config.json`. For example, a local [GroktoCrawl](https://github.com/groktopus/groktocrawl) instance listening on `127.0.0.1:8080` can be used without adding a separate provider:

```json
{
  "firecrawl": {
    "api_url": "http://127.0.0.1:8080/v2/search",
    "scrape_url": "http://127.0.0.1:8080/v2/scrape"
  }
}
```

Keep `FIRECRAWL_API_KEY` configured if your backend enforces bearer authentication; local development instances may ignore the header. This does not make GroktoCrawl the default and does not claim coverage for every Firecrawl endpoint.

## 🛠 MCP Tool Reference

This MCP server exposes exactly two stable, source-only tools: `web_search` and `web_extract`. Use `web_search` for source discovery and let the MCP host synthesize from those sources when needed; the server itself does not generate answers or truth claims.

The Hermes plugin exposes the same stable capability as `web_search_plus` and `web_extract_plus`; the names differ because MCP and Hermes use different tool surfaces.

### `web_search`

Use for source discovery, current events, prices, weather, sports lineups, schedules, and whenever you want the raw search landscape first.

Parameters:

- `query` — required search query
- `provider` — `auto`, `serper`, `serpbase`, `brave`, `tavily`, `querit`, `linkup`, `exa`, `firecrawl`, `parallel`, `you`, `searxng`, `keenable`
- `count` — results to return, default `5`, max `20`
- `depth` — Exa depth: `normal`, `deep`, `deep-reasoning`
- `time_range` — `hour`, `day`, `week`, `month`, `year`
- `freshness` — unified `day`, `week`, `month`, or `year` recency request
- `search_type` — `search` or Serper-native `news`
- `country` / `language` — explicit locale overrides
- `include_domains` / `exclude_domains` — domain allow/deny lists
- `mode` — `normal` or `research`
- `quality_report` — include routing/result diagnostics
- `research_time_budget` — best-effort wall-clock budget for research mode

Example MCP arguments:

```json
{
  "query": "latest AI hardware news",
  "provider": "auto",
  "count": 5,
  "quality_report": true
}
```

### `web_extract`

Parameters:

- `urls` — required list of URLs
- `provider` — `auto`, `tavily`, `exa`, `linkup`, `parallel`, `firecrawl`, `you`, `keenable`, `serper`
- `format` — `markdown` or `html`
- `include_images` — include image metadata when supported
- `include_raw_html` — include raw HTML when supported
- `render_js` — render JavaScript before extraction when supported

Example MCP arguments:

```json
{
  "urls": ["https://example.com"],
  "provider": "auto",
  "format": "markdown"
}
```

## 🧠 Classic Routing v2 examples

- `東京 AI ニュース 今日` → You.com multilingual/current search
- `arXiv 2024 LLM scaling laws` → Exa academic discovery
- `CVE-2025 openssl advisory` → Serper security/current search
- `best bookshelf speakers under 1000 EUR Austria` → Serper/Firecrawl shopping/local search
- `open source alternatives to Linear` → Exa/Firecrawl OSS discovery
- `recent RAG vs fine-tuning benchmark sources` → source-result discovery; the MCP host may synthesize from returned sources

Guarded providers can still be called explicitly. To let one participate in `provider="auto"`, opt in:

```bash
web-search-plus-mcp config set-auto-allow parallel on
web-search-plus-mcp config set-auto-allow parallel off
```

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest tests/ -q -p no:cacheprovider
ruff check .
python -m build
```

The GitHub Actions workflow runs the test suite on Python 3.10, 3.11, and 3.12, then verifies Ruff, byte-compilation, wheel creation, and source-distribution creation.

## Credits

Built on the Web Search Plus routing engine and packaged as a standalone MCP server.

## License

MIT © 2026 robbyczgw-cla
