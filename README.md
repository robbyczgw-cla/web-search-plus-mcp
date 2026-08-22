# 🔍 web-search-plus-mcp

<p align="center">
  <img src="docs/assets/web-search-plus-logo.png" alt="Web Search Plus" width="180">
</p>

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![CI](https://github.com/robbyczgw-cla/web-search-plus-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/robbyczgw-cla/web-search-plus-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Glama](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp/badge)](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp)

**Give your AI app better web search and clean page reading.** `web-search-plus-mcp` works with Claude Desktop, Cursor, NanoBot, Hermes, and other MCP apps. It searches across the services you choose, returns the original sources, and can try another service when one fails.

`web-search-plus-mcp 4.0.2` adds Parallel Search modes (`turbo`, `fast`, `basic`, `advanced`, default `fast`) and lets Parallel join automatic routing when a key is configured. 4.0.1 hardened the DonSeTch stdio session, cleanup, and binary readiness reporting and tests against DonSeTch 2.3.1. 4.0.0 removed the optional Hound provider and added the DonSeTch stdio provider while keeping the stable source-only MCP tools and routing surface.

## 🚀 Quick Start

```bash
# Run it without installing anything
uvx web-search-plus-mcp

# Or install it normally
pip install web-search-plus-mcp
web-search-plus-mcp
```

Add at least one search provider. You can start with one and add more later.

## ✨ What it does

- **15 search providers** — use one service or let Web Search Plus choose
- **9 page-reading providers** — turn web pages into clean text
- **Automatic fallback** — try another provider when the first one fails
- **Real sources** — keep the links and text the result came from
- **Research mode** — search several providers for broader questions
- **Optional details** — see which provider ran and how the result was found
- **Simple setup tools** — check your config and create a starter setup
- **Optional local search** — connect a separately installed DonSeTch executable through the WSP provider adapter

Version 4.0.2 adds Parallel Search modes (default `fast`). Version 4.0.1 hardens DonSeTch process reuse and diagnostics. Version 4.0.0 removed the optional Hound provider and added the separately installed DonSeTch 2.1.0 stdio adapter. See the [4.0.0 release notes](docs/RELEASE_4_0_0.md) and [DonSeTch guide](docs/DONSETCH.md) for migration, licensing, and runtime boundaries.

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

## 🧩 Agent Plugins package

This repository also contains a portable [Agent Plugins 1.0](https://agent-plugins.org/) package for clients that support the standard. The root [`plugin.json`](plugin.json) describes the plugin and [`mcp.json`](mcp.json) connects the MCP server through the published PyPI package.

The portable configuration uses `uvx` with an exact `web-search-plus-mcp` version pin. Install [uv](https://docs.astral.sh/uv/) first, then load this repository as an Agent Plugin in a compatible client such as VS Code, Cursor, GitHub Copilot, ChatGPT/Codex, or Kiro. Provider credentials are deliberately not stored in the plugin manifest; provide the required environment variables through the client or process environment.

The Agent Plugins format defines packaging and loading, not a central marketplace. Client-specific discovery and distribution remain outside the portable package contract.

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

## 🔌 MCP protocol compatibility

The server uses MCP Python SDK v2 and keeps the stdio boundary dual-era compatible:

- modern clients negotiate the stateless MCP `2026-07-28` protocol through `server/discover`
- legacy handshake clients continue to negotiate MCP `2025-11-25`

The package exposes stdio only; the specification's Streamable HTTP session removal, subscriptions, OAuth changes, tasks, and multi-round-trip requests do not alter the two-tool Web Search Plus surface. Both protocol paths are covered by real subprocess tests.

## 🔎 Search Providers

- **You.com** — fast source-result provider for current and multilingual search
- **Serper** — Google-style facts, news, shopping, local queries
- **Exa** — semantic discovery, GitHub/docs, arXiv/academic, and OSS discovery
- **Firecrawl** — web search plus scrape-ready content
- **Parallel** — LLM-ready web search with long excerpts; joins automatic routing when a key is configured (`PARALLEL_API_KEY`)
- **Tavily** — research and analysis
- **Linkup** — source-backed grounding/citations
- **Brave** — explicit-only independent web index by default (`BRAVE_API_KEY`, `auto_allow=false`)
- **SearXNG** — privacy-first self-hosted meta-search
- **SerpBase** — explicit-only Google SERP API (`SERPBASE_API_KEY`, `auto_allow=false`)
- **Querit** — explicit-only multilingual, real-time AI search (`QUERIT_API_KEY`, `auto_allow=false`)
- **Keenable** — independent web index with search and extraction (`KEENABLE_API_KEY`, or opt-in keyless public tier; off by default)
- **DonSeTch** — explicit-only local Search/Fetch provider through a separately installed stdio executable (`DONSETCH_BIN`)
- **Octen via Monid** — explicit-only source-result web search with native recency and domain filters (`MONID_API_KEY`, `auto_allow=false`)
- **TinyFish** — explicit-only BYOK source-result search (`TINYFISH_API_KEY`, `auto_allow=false`)

### Octen source search via Monid

The adapter executes Octen's `/search` endpoint through [Monid's documented HTTP API](https://docs.monid.ai/api/run.html) for ranked links and highlights. It explicitly disables full-content retrieval and does not call Octen's answer or Broad Search APIs. Configure `MONID_API_KEY` from [Monid](https://app.monid.ai/access/api-keys), then select `provider="octen"`; automatic routing remains unchanged unless you deliberately enable `auto_allow`. Access and billing use Monid's prepaid wallet; see Monid for current pricing and terms.

### TinyFish source search

Configure your own `TINYFISH_API_KEY` and select `provider="tinyfish"`; TinyFish remains outside automatic routing and fallback. Web Search Plus MCP does not provide, pool, proxy, or share TinyFish credentials. Review the [TinyFish Search API reference](https://docs.tinyfish.ai/search-api/reference) and [TinyFish Terms](https://www.tinyfish.ai/terms) before use: the published Terms grant broad rights over Customer Data, including queries, for analysis, training, fine-tuning, evaluation, and model improvement. This integration therefore treats TinyFish as high risk and makes no no-training claim.

## 📄 Extract Providers

- **Tavily** — public default first choice; fastest reliable extraction in the v2.1 benchmark
- **Exa** — fast contents API, strong for docs/academic pages
- **Linkup** — clean markdown and source-grounded fetches
- **Parallel** — docs-focused fallback with full-content defaults of 60k characters per result / 120k total
- **Firecrawl** — robust scrape fallback, useful for JS-heavy/blocked pages
- **You.com** — LLM-ready snippets/content where available
- **Keenable** — keyed or explicitly opted-in public extraction
- **Serper** — fast webpage scraper extraction
- **DonSeTch** — explicit-only local Markdown fetch through a separately installed stdio executable

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

### DonSeTch local provider

[DonSeTch](https://github.com/dondai44423/donsetch) 2.3.1 is an independent
AGPL-3.0-only project. It is not bundled with this package. Web Search Plus
starts the separately installed executable as a stdio MCP process using
`DONSETCH_BIN` and projects its `web_search` and `web_fetch` results into the
normal source-only envelopes.

DonSeTch remains `explicit-only` unless the operator enables `auto_allow`. The
adapter was tested for stdio initialization, Search, Fetch, and structured
errors; browser-based retrieval depends on the host environment and is not
guaranteed.

See the [DonSeTch setup and security guide](docs/DONSETCH.md) for installation,
configuration, licensing, migration, and tested boundaries.

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
- `provider` — `auto`, `serper`, `serpbase`, `brave`, `tavily`, `querit`, `linkup`, `exa`, `firecrawl`, `parallel`, `you`, `searxng`, `keenable`, `donsetch`, `octen`, `tinyfish`
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
- `provider` — `auto`, `tavily`, `exa`, `linkup`, `parallel`, `firecrawl`, `you`, `keenable`, `serper`, `donsetch`
- `format` — `markdown` or `html`
- `include_images` — include image metadata when supported
- `include_raw_html` — include raw HTML when supported
- `render_js` — render JavaScript before extraction when supported
- `spans` — select deterministic semantic spans from extracted text
- `spans_query` — optional query used to rank semantic spans

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
web-search-plus-mcp config set-auto-allow donsetch on
web-search-plus-mcp config set-auto-allow donsetch off
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for project boundaries, portable-engine sync rules, provider requirements, security constraints, and pull-request expectations.

Run the same gates as CI:

```bash
python -m pip install --upgrade pip build
python -m pip install -e ".[test]"
python -m pytest tests/ -q -p no:cacheprovider
ruff check --config pyproject.toml .
python -m compileall -q web_search_plus_mcp tests
python scripts/gen_contract_v3_schemas.py --check
python -m build
```

The GitHub Actions workflow runs the test suite on Python 3.10, 3.11, and 3.12, then verifies Ruff, byte-compilation, wheel creation, source-distribution creation, and wheel/sdist parity.

## Credits

Built on the Web Search Plus routing engine and packaged as a standalone MCP server.

## License

MIT © 2026 robbyczgw-cla
