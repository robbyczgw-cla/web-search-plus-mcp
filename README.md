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

Version note: `web-search-plus-mcp` uses its own MCP package version (`0.5.0`) while tracking the Web Search Plus engine family (`v1.9.x`). The Hermes plugin is versioned separately as `hermes-web-search-plus v1.9.x`.

## ✨ Features

- **10 search providers** — Serper, Brave, Tavily, Exa, Querit, Linkup, Firecrawl, Perplexity, You.com, SearXNG
- **5 extract providers** — Linkup, Firecrawl, Tavily, Exa, You.com
- **Optional beta `web_answer`** — cited source-backed briefs when you explicitly want synthesis instead of raw results
- **Intelligent auto-routing** — scores query intent and picks a provider automatically
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

The recommended starter preset is **Tavily + Linkup + Brave**. It gives a practical baseline for search, extraction, and cited-answer experiments without wiring every provider on day one.

Add `--enable-answer` if you want the generated `.env` and snippet to opt into the beta `web_answer` tool:

```bash
web-search-plus-mcp setup --preset starter --enable-answer
```

`status` returns a non-zero exit code when no search provider is configured, which makes it usable as a config check in scripts.

Persistent routing preferences live in `config.json` rather than `.env`:

```bash
web-search-plus-mcp config show
web-search-plus-mcp config set-default brave      # strict fixed-provider mode
web-search-plus-mcp config set-routing on         # restore auto-routing
web-search-plus-mcp config set-priority tavily,linkup,brave
web-search-plus-mcp config set-fallback tavily
web-search-plus-mcp config disable perplexity
web-search-plus-mcp config enable perplexity
web-search-plus-mcp config set-threshold 0.45
web-search-plus-mcp config reset --yes
```

Use `--config-path /path/to/config.json` or `WEB_SEARCH_PLUS_CONFIG=/path/to/config.json` for isolated MCP host installs. Provider secrets stay in environment variables; routing behavior stays in `config.json`.

Other presets:

- `minimal` — Brave only
- `lean` — Tavily + Linkup
- `starter` — Tavily + Linkup + Brave
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
        "LINKUP_API_KEY": "your_linkup_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "BRAVE_API_KEY": "your_brave_key"
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

- **Serper** — Google-style facts, news, shopping, local queries
- **Brave** — general-purpose independent web index
- **Tavily** — research and analysis
- **Exa** — semantic discovery, similarity, deep/deep-reasoning synthesis
- **Querit** — multilingual, real-time AI search
- **Linkup** — source-backed grounding/citations
- **Firecrawl** — web search plus scrape-ready content
- **Perplexity** — direct synthesized answers
- **You.com** — LLM-ready real-time snippets
- **SearXNG** — privacy-first self-hosted meta-search

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
- `provider` — `auto`, `serper`, `brave`, `tavily`, `exa`, `querit`, `linkup`, `firecrawl`, `perplexity`, `you`, `searxng`
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
  "query": "latest Hermes Agent release",
  "provider": "linkup",
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
    "LINKUP_API_KEY": "your_linkup_key",
    "TAVILY_API_KEY": "your_tavily_key"
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

## 🧠 Auto-Routing Examples

- `iPhone 16 Pro price` → Serper/Brave shopping-style search
- `how does TCP/IP work` → Tavily research-style search
- `latest multilingual EV market updates` → Querit/Linkup real-time/source-backed search
- `companies like Stripe` → Exa discovery search
- `what is quantum computing` → Perplexity/You.com direct-answer style search
- `privacy focused search results` → SearXNG when configured

## Credits

Built on the Web Search Plus routing logic originally developed for OpenClaw/Clawhub and later ported to Hermes as `hermes-web-search-plus`.

## License

MIT © 2026 robbyczgw-cla
