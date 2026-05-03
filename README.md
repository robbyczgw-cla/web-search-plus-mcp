# 🔍 web-search-plus-mcp

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Glama](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp/badge)](https://glama.ai/mcp/servers/robbyczgw-cla/web-search-plus-mcp)

**Multi-provider web search and extraction MCP server with intelligent auto-routing.**

`web-search-plus-mcp` is the standalone MCP packaging of Web Search Plus. It gives Claude Desktop, NanoBot, Cursor, and other MCP-compatible hosts access to the same Python routing engine family used by the Hermes/OpenClaw Web Search Plus tools.

## ✨ Features

- **10 search providers** — Serper, Brave, Tavily, Exa, Querit, Linkup, Firecrawl, Perplexity, You.com, SearXNG
- **5 extract providers** — Firecrawl, Linkup, Tavily, Exa, You.com
- **Intelligent auto-routing** — scores query intent and picks a provider automatically
- **Quality reports** — optional routing/result diagnostics
- **Research mode** — opt-in multi-provider search + top-source extraction with a time budget
- **Zero-install run** — `uvx web-search-plus-mcp`
- **MCP-native** — stdio server exposing `web_search` and `web_extract`

## 🚀 Quick Start

```bash
# Run instantly with uvx
uvx web-search-plus-mcp

# Or install globally
pip install web-search-plus-mcp
web-search-plus-mcp
```

At least one provider credential is required for search. Extraction needs at least one extraction-capable provider key.

## ⚙️ Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\\Claude\\claude_desktop_config.json` on Windows:

```json
{
  "mcpServers": {
    "web-search-plus": {
      "command": "uvx",
      "args": ["web-search-plus-mcp"],
      "env": {
        "LINKUP_API_KEY": "your_linkup_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "EXA_API_KEY": "your_exa_key",
        "FIRECRAWL_API_KEY": "your_firecrawl_key",
        "BRAVE_API_KEY": "your_brave_key",
        "SERPER_API_KEY": "your_serper_key",
        "QUERIT_API_KEY": "your_querit_key",
        "PERPLEXITY_API_KEY": "your_perplexity_key",
        "YOU_API_KEY": "your_you_key",
        "SEARXNG_INSTANCE_URL": "https://your-searxng-instance.example.com"
      }
    }
  }
}
```

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

### `web_search`

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
