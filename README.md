# 🔍 web-search-plus-mcp

<p align="center">
  <img src="docs/assets/web-search-plus-logo.png" alt="web search plus logo" width="180">
</p>

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Glama](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp/badge)](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp)

**Multi-provider web search and Parallel-aware URL extraction for MCP clients.**

`web-search-plus-mcp` is the standalone MCP packaging of Web Search Plus. It gives Claude Desktop, Cursor, NanoBot, Hermes native MCP, and other MCP-compatible hosts the same provider family used by the Hermes/OpenClaw Web Search Plus tools.

Version note: `web-search-plus-mcp` uses its own MCP package version (`0.9.0`) while tracking the Web Search Plus v2.2 engine family. The plugin package is versioned separately as `hermes-web-search-plus v2.2.x`.

## ✨ Features

- **13 search providers** — Serper, Brave, Tavily, Exa, Linkup, Firecrawl, Parallel, native Perplexity, Kilo Perplexity, You.com, SearXNG, SerpBase, Querit
- **6 extract providers** — Tavily, Exa, Linkup, Parallel, Firecrawl, You.com
- **Routing v2 auto-routing** — class-aware routing for multilingual/current, docs/API, arXiv, CVE/security, local/shopping, OSS discovery, and answer/synthesis queries
- **Quality reports** — optional routing/result diagnostics
- **Research mode** — opt-in multi-provider search + top-source extraction with a time budget
- **Onboarding CLI** — `status`, `list`, `setup`, and persistent routing `config` helpers for MCP env/config wiring
- **Zero-install run** — `uvx web-search-plus-mcp`
- **MCP-native** — stdio server exposing stable `web_search` and `web_extract` tools

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

The recommended starter preset is **You.com + Serper + Linkup**. It gives a practical Routing v2 baseline for fast current search, Google-style discovery, and extraction workflows without wiring every provider on day one.


`status` returns a non-zero exit code when no search provider is configured, which makes it usable as a config check in scripts.

Persistent routing preferences live in `config.json` rather than `.env`:

```bash
web-search-plus-mcp config show
web-search-plus-mcp config set-default you        # strict fixed-provider mode
web-search-plus-mcp config set-routing on         # restore Routing v2 auto-routing
web-search-plus-mcp config set-priority you,serper,exa,firecrawl,tavily,linkup,parallel
web-search-plus-mcp config set-fallback serper
web-search-plus-mcp config disable perplexity
web-search-plus-mcp config enable perplexity
web-search-plus-mcp config disable kilo-perplexity
web-search-plus-mcp config set-threshold 0.45
web-search-plus-mcp config reset --yes
```

Use `--config-path /path/to/config.json` or `WEB_SEARCH_PLUS_CONFIG=/path/to/config.json` for isolated MCP host installs. Provider secrets stay in environment variables; routing behavior stays in `config.json`.

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

- **You.com** — fast Routing v2 core provider for current, multilingual, and answer-shaped snippets
- **Serper** — Google-style facts, news, shopping, local queries
- **Exa** — semantic discovery, GitHub/docs, arXiv/academic, and OSS discovery
- **Firecrawl** — web search plus scrape-ready content
- **Parallel** — explicit-only LLM-ready web search with long excerpts (`PARALLEL_API_KEY`, `auto_allow=false`)
- **Tavily** — research and analysis
- **Linkup** — source-backed grounding/citations
- **Brave** — explicit-only independent web index by default (`BRAVE_API_KEY`, `auto_allow=false`)
- **Perplexity** — explicit-only native Perplexity API synthesized answers (`PERPLEXITY_API_KEY`, `sonar-pro`, `auto_allow=false`)
- **Kilo Perplexity** — explicit-only Perplexity via Kilo gateway (`KILOCODE_API_KEY`, `perplexity/sonar-pro`, `auto_allow=false`)
- **SearXNG** — privacy-first self-hosted meta-search
- **SerpBase** — explicit-only Google SERP API (`SERPBASE_API_KEY`, `auto_allow=false`)
- **Querit** — explicit-only multilingual, real-time AI search (`QUERIT_API_KEY`, `auto_allow=false`)

## 📄 Extract Providers

- **Tavily** — default first choice; fastest reliable extraction in the v2.1 benchmark
- **Exa** — fast contents API, strong for docs/academic pages
- **Linkup** — clean markdown and source-grounded fetches
- **Parallel** — fast excerpt-rich docs fallback with optional full-content extraction
- **Firecrawl** — robust scrape fallback, useful for JS-heavy/blocked pages
- **You.com** — LLM-ready snippets/content where available

## 🛠 MCP Tool Reference

This MCP server exposes stable `web_search` and `web_extract` tools. The old beta `web_answer` tool was removed to match Web Search Plus v2.1: use `web_search` for source discovery and let the MCP host synthesize from results when needed.

The Hermes plugin exposes the same stable capability as `web_search_plus` and `web_extract_plus`; the names differ because MCP and Hermes use different tool surfaces.

### `web_search`

Use for source discovery, current events, prices, weather, sports lineups, schedules, and whenever you want the raw search landscape first.

Parameters:

- `query` — required search query
- `provider` — `auto`, `serper`, `brave`, `tavily`, `exa`, `linkup`, `firecrawl`, `parallel`, `perplexity`, `kilo-perplexity`, `you`, `searxng`, `serpbase`, `querit`
- `count` — results to return, default `5`, max `20`
- `depth` — Exa depth: `normal`, `deep`, `deep-reasoning`
- `time_range` — `hour`, `day`, `week`, `month`, `year`
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
- `provider` — `auto`, `tavily`, `exa`, `linkup`, `parallel`, `firecrawl`, `you`
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

## 🧠 Routing v2 Examples

- `東京 AI ニュース 今日` → You.com multilingual/current search
- `arXiv 2024 LLM scaling laws` → Exa academic discovery
- `CVE-2025 openssl advisory` → Serper security/current search
- `best bookshelf speakers under 1000 EUR Austria` → Serper/Firecrawl shopping/local search
- `open source alternatives to Linear` → Exa/Firecrawl OSS discovery
- `summarize the tradeoffs of RAG vs fine-tuning` → You.com with synthesis hint metadata for the MCP host

Guarded providers can still be called explicitly. To let one participate in `provider="auto"`, opt in:

```bash
web-search-plus-mcp config set-auto-allow parallel on
web-search-plus-mcp config set-auto-allow parallel off
```

## Credits

Built on the Web Search Plus routing engine and packaged as a standalone MCP server.

## License

MIT © 2026 robbyczgw-cla
