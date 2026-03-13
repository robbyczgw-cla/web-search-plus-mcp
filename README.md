# 🔍 web-search-plus-mcp

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Multi-provider web search MCP server with intelligent auto-routing.**

A [Model Context Protocol](https://modelcontextprotocol.io/) server that gives AI assistants access to 7 search providers with intelligent auto-routing. Analyzes query intent and picks the best provider automatically — no manual switching needed. Install, configure your keys, and go.

## ✨ Features

- **Intelligent auto-routing** — analyzes query intent and picks the best provider automatically
- **7 search providers** — use one or all, graceful fallback if any key is missing
- **Zero install option** — run instantly with `uvx web-search-plus-mcp`
- **MCP-native** — works with Claude Desktop, NanoBot, and any MCP-compatible host

## 🔎 Supported Providers

| Provider | Best for | Free tier |
|----------|----------|-----------|
| **Serper** (Google) | Facts, news, shopping, local businesses | 2,500 queries/month |
| **Tavily** | Deep research, analysis, explanations | 1,000 queries/month |
| **Querit** | Multi-lingual AI search with rich metadata and real-time info | 1,000 queries/month |
| **Exa** (Neural) | Semantic discovery, finding similar content | 1,000 queries/month |
| **Perplexity** | AI-synthesized answers with citations | Via API key |
| **You.com** | Real-time RAG, LLM-ready snippets | Limited free tier |
| **SearXNG** | Privacy-first, self-hosted, $0 cost | Free (self-hosted) |

## 🧠 Auto-Routing Examples

| Query | Routed to | Why |
|-------|-----------|-----|
| "iPhone 16 Pro price" | Serper | Shopping intent detected |
| "how does TCP/IP work" | Tavily | Research/explanation intent |
| "latest multilingual EV market updates" | Querit | Real-time AI search |
| "companies like Stripe" | Exa | Discovery/semantic intent |
| "what is quantum computing" | Perplexity | Direct answer intent |

## 🚀 Quick Start

```bash
# Run instantly with uvx (no install needed)
uvx web-search-plus-mcp

# Or install globally with pip
pip install web-search-plus-mcp
web-search-plus-mcp
```

## ⚙️ Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "web-search-plus": {
      "command": "uvx",
      "args": ["web-search-plus-mcp"],
      "env": {
        "SERPER_API_KEY": "your_serper_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "QUERIT_API_KEY": "your_querit_key",
        "EXA_API_KEY": "your_exa_key",
        "PERPLEXITY_API_KEY": "your_perplexity_key",
        "YOU_API_KEY": "your_you_key",
        "SEARXNG_BASE_URL": "https://your-searxng-instance.example.com"
      }
    }
  }
}
```

## 🤖 NanoBot Config

Add to your NanoBot `config.json` under `mcp_servers`:

```json
{
  "mcp_servers": [
    {
      "name": "web-search-plus",
      "command": "uvx",
      "args": ["web-search-plus-mcp"],
      "env": {
        "SERPER_API_KEY": "your_serper_key",
        "TAVILY_API_KEY": "your_tavily_key",
        "QUERIT_API_KEY": "your_querit_key",
        "EXA_API_KEY": "your_exa_key",
        "PERPLEXITY_API_KEY": "your_perplexity_key",
        "YOU_API_KEY": "your_you_key",
        "SEARXNG_BASE_URL": "https://your-searxng-instance.example.com"
      }
    }
  ]
}
```

## 🔑 Environment Variables

| Variable | Provider | Sign up |
|----------|----------|---------|
| `SERPER_API_KEY` | Serper (Google) | [console.serper.dev](https://console.serper.dev) |
| `TAVILY_API_KEY` | Tavily | [tavily.com](https://tavily.com) |
| `QUERIT_API_KEY` | Querit | [querit.ai](https://querit.ai) |
| `EXA_API_KEY` | Exa | [exa.ai](https://exa.ai) |
| `PERPLEXITY_API_KEY` | Perplexity | [docs.perplexity.ai](https://docs.perplexity.ai) |
| `YOU_API_KEY` | You.com | [you.com/api](https://you.com/api) |
| `SEARXNG_BASE_URL` | SearXNG (self-hosted) | [docs.searxng.org](https://docs.searxng.org) |

At least one provider is required. More providers = better routing coverage. SearXNG needs no API key — just point `SEARXNG_BASE_URL` at your self-hosted instance.

You can also drop a `.env` file next to the server:

```env
SERPER_API_KEY=xxx
TAVILY_API_KEY=xxx
QUERIT_API_KEY=xxx
EXA_API_KEY=xxx
PERPLEXITY_API_KEY=xxx
YOU_API_KEY=xxx
SEARXNG_BASE_URL=https://your-searxng-instance.example.com
```

## 🛠 Tool Reference

### `web_search`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | *required* | Search query |
| `provider` | string | `"auto"` | Force a provider: `auto`, `serper`, `tavily`, `querit`, `exa`, `perplexity`, `you`, `searxng` |
| `count` | integer | `5` | Number of results to return |

## Credits

Built on the **[web-search-plus](https://clawhub.com/skills/web-search-plus)** routing logic — a multi-provider search skill for OpenClaw with intelligent auto-routing.

## License

MIT © 2026 robbyczgw-cla
