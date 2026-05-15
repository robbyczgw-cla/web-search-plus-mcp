# 🔍 web-search-plus-mcp

<p align="center">
  <img src="docs/assets/web-search-plus-logo.png" alt="web search plus logo" width="180">
</p>

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Glama](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp/badge)](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp)

**Multi-provider web search, URL extraction, and optional cited answers for MCP clients.**

`web-search-plus-mcp` is the standalone MCP packaging of Web Search Plus. It gives Claude Desktop, Cursor, NanoBot, Hermes native MCP, and other MCP-compatible hosts the same provider family used by the Hermes/OpenClaw Web Search Plus tools.

Version note: `web-search-plus-mcp` uses its own MCP package version (`0.7.0`) while tracking the Web Search Plus Routing v2 engine family (`v2.0.x`). The plugin package is versioned separately as `hermes-web-search-plus v2.0.x`.

## ✨ Features

- **12 search providers** — Serper, Brave, Tavily, Exa, Linkup, Firecrawl, native Perplexity, Kilo Perplexity, You.com, SearXNG, SerpBase, Querit
- **5 extract providers** — Linkup, Firecrawl, Tavily, Exa, You.com
- **Optional beta `web_answer`** — cited source-backed briefs when you explicitly want synthesis instead of raw results
- **Routing v2 auto-routing** — class-aware routing for multilingual/current, docs/API, arXiv, CVE/security, local/shopping, OSS discovery, and answer/synthesis queries
- **Quality reports** — optional routing/result diagnostics
- **Research mode** — opt-in multi-provider search + top-source extraction with a time budget
- **Onboarding CLI** — `status`, `list`, `setup`, and persistent routing `config` helpers for MCP env/config wiring
- **Zero-install run** — `uvx web-search-plus-mcp`
- **MCP-native** — stdio server exposing `web_search`, `web_extract`, and opt-in `web_answer`

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

The recommended starter preset is **You.com + Serper + Linkup**. It gives a practical Routing v2 baseline for fast current search, Google-style discovery, and clean extraction/citation workflows without wiring every provider on day one.

Add `--enable-answer` if you want the generated `.env` and snippet to opt into the beta `web_answer` tool:

```bash
web-search-plus-mcp setup --preset starter --enable-answer
```

`status` returns a non-zero exit code when no search provider is configured, which makes it usable as a config check in scripts.

Persistent routing preferences live in `config.json` rather than `.env`:

```bash
web-search-plus-mcp config show
web-search-plus-mcp config set-default you        # strict fixed-provider mode
web-search-plus-mcp config set-routing on         # restore Routing v2 auto-routing
web-search-plus-mcp config set-priority you,serper,exa,firecrawl,tavily,linkup
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

`WSP_ENABLE_WEB_ANSWER=1` is optional. Without it, the MCP server exposes only the stable `web_search` and `web_extract` tools.

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
- **Tavily** — research and analysis
- **Linkup** — source-backed grounding/citations
- **Brave** — explicit-only independent web index by default (`BRAVE_API_KEY`, `auto_allow=false`)
- **Perplexity** — explicit-only native Perplexity API synthesized answers (`PERPLEXITY_API_KEY`, `sonar-pro`, `auto_allow=false`)
- **Kilo Perplexity** — explicit-only Perplexity via Kilo gateway (`KILOCODE_API_KEY`, `perplexity/sonar-pro`, `auto_allow=false`)
- **SearXNG** — privacy-first self-hosted meta-search
- **SerpBase** — explicit-only Google SERP API (`SERPBASE_API_KEY`, `auto_allow=false`)
- **Querit** — explicit-only multilingual, real-time AI search (`QUERIT_API_KEY`, `auto_allow=false`)

## 📄 Extract Providers

- **Linkup** — recommended first choice for clean markdown and low cost
- **Firecrawl** — robust scrape fallback, useful for JS-heavy/blocked pages
- **Tavily** — extraction/content API
- **Exa** — contents API
- **You.com** — LLM-ready snippets/content where available

## 🛠 MCP Tool Reference

This MCP server exposes `web_search` and `web_extract` by default. It exposes `web_answer` only when `WSP_ENABLE_WEB_ANSWER=1` is set.

The Hermes plugin exposes the same capability as `web_search_plus`, `web_extract_plus`, and `web_answer_plus`; the names differ because MCP and Hermes use different tool surfaces.

### `web_search`

Use for source discovery, current events, prices, weather, sports lineups, schedules, and whenever you want the raw search landscape first.

Parameters:

- `query` — required search query
- `provider` — `auto`, `serper`, `brave`, `tavily`, `exa`, `linkup`, `firecrawl`, `perplexity`, `kilo-perplexity`, `you`, `searxng`, `serpbase`, `querit`
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
- `provider` — `auto`, `firecrawl`, `linkup`, `tavily`, `exa`, `you`
- `format` — `markdown` or `html`
- `include_images` — include image metadata when supported
- `include_raw_html` — include raw HTML when supported
- `render_js` — render JavaScript before extraction when supported

Example MCP arguments:

```json
{
  "urls": ["https://example.com"],
  "provider": "linkup",
  "format": "markdown"
}
```

### `web_answer` optional beta

Use when you specifically want a short cited synthesis. Do **not** use it as a default replacement for `web_search`.

`web_answer` is slower than `web_search` because it searches, selects sources, and may extract top URLs. Its freshness default is `none` to avoid over-triggering recency filters on evergreen questions.

Parameters:

- `query` — required question/topic
- `mode` — `quick` or `deep`, default `quick`
- `sources` — citation-ready source target, default `3`, max `10`
- `freshness` — `none`, `auto`, `day`, `week`, `month`, `year`, default `none`
- `max_extracts` — top URLs to extract, default `2`, max `5`
- `output` — `answer`, `brief`, `sources`, or `json`

Enable it:

```json
{
  "env": {
    "WSP_ENABLE_WEB_ANSWER": "1",
    "YOU_API_KEY": "your_you_key",
    "LINKUP_API_KEY": "your_linkup_key"
  }
}
```

Example MCP arguments:

```json
{
  "query": "What changed in Hermes Agent's latest release?",
  "mode": "quick",
  "sources": 3,
  "freshness": "none"
}
```

## 🧠 Routing v2 Examples

- `東京 AI ニュース 今日` → You.com multilingual/current search
- `arXiv 2024 LLM scaling laws` → Exa academic discovery
- `CVE-2025 openssl advisory` → Serper security/current search
- `best bookshelf speakers under 1000 EUR Austria` → Serper/Firecrawl shopping/local search
- `open source alternatives to Linear` → Exa/Firecrawl OSS discovery
- `summarize the tradeoffs of RAG vs fine-tuning` → You.com with `answer_mode_recommended=true`

Guarded providers can still be called explicitly. To let one participate in `provider="auto"`, opt in:

```bash
web-search-plus-mcp config set-auto-allow serpbase on
web-search-plus-mcp config set-auto-allow serpbase off
```

## Credits

Built on the Web Search Plus routing engine and packaged as a standalone MCP server.

## License

MIT © 2026 robbyczgw-cla
