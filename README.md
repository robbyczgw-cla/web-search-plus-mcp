# web-search-plus-mcp

[![PyPI version](https://img.shields.io/pypi/v/web-search-plus-mcp.svg)](https://pypi.org/project/web-search-plus-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A **Model Context Protocol (MCP) server** that gives AI assistants access to multi-provider web search with intelligent auto-routing. Automatically selects the best search provider based on query intent — no manual switching needed.

## Features

- 🔍 **Intelligent auto-routing** — picks the right provider per query
- ⚡ **Zero config** — `uvx web-search-plus-mcp` and you're done
- 🔌 **MCP-native** — works with Claude Desktop, NanoBot, and any MCP host
- 🔑 **Bring your own keys** — use whichever providers you have

## Quick Start

```bash
# Run directly with uvx (no install needed)
uvx web-search-plus-mcp

# Or install globally
pip install web-search-plus-mcp
web-search-plus-mcp
```

## Provider Routing

| Provider | Best For | Config |
|----------|----------|--------|
| **Serper** (Google) | General search, news, current events | `SERPER_API_KEY` |
| **Tavily** | Research, deep content extraction | `TAVILY_API_KEY` |
| **Exa** | Neural / semantic / discovery search | `EXA_API_KEY` |
| **Querit** | Multilingual AI search | `QUERIT_API_KEY` |
| **Perplexity** | AI-powered answers | `PERPLEXITY_API_KEY` |
| **You.com** | RAG / real-time search | `YOU_API_KEY` |
| **SearXNG** | Self-hosted / privacy-first | `SEARXNG_BASE_URL` |

Auto-routing picks the best provider per query: Serper for news/general, Tavily for research/analysis, Exa for discovery/semantic, Querit for multilingual, Perplexity for AI-powered answers, You.com for RAG/real-time, and SearXNG for privacy-first or self-hosted setups. Falls back gracefully if a provider key is missing.

## Claude Desktop Config

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
        "EXA_API_KEY": "your_exa_key",
        "QUERIT_API_KEY": "your_querit_key",
        "PERPLEXITY_API_KEY": "your_perplexity_key",
        "YOU_API_KEY": "your_you_key",
        "SEARXNG_BASE_URL": "https://your-searxng-instance.example.com"
      }
    }
  }
}
```

## NanoBot Config

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
        "EXA_API_KEY": "your_exa_key",
        "QUERIT_API_KEY": "your_querit_key",
        "PERPLEXITY_API_KEY": "your_perplexity_key",
        "YOU_API_KEY": "your_you_key",
        "SEARXNG_BASE_URL": "https://your-searxng-instance.example.com"
      }
    }
  ]
}
```

## API Keys

| Provider | Free Tier | Get Key / Config |
|----------|-----------|-----------------|
| Serper | 2,500 free searches/month | [serper.dev](https://serper.dev) → `SERPER_API_KEY` |
| Tavily | 1,000 free searches/month | [tavily.com](https://tavily.com) → `TAVILY_API_KEY` |
| Exa | 1,000 free searches/month | [exa.ai](https://exa.ai) → `EXA_API_KEY` |
| Querit | Free tier available | [querit.ai](https://querit.ai) → `QUERIT_API_KEY` |
| Perplexity | Free tier available | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) → `PERPLEXITY_API_KEY` |
| You.com | Free tier available | [you.com/api](https://you.com/api) → `YOU_API_KEY` |
| SearXNG | Self-hosted, free | Set `SEARXNG_BASE_URL` to your instance URL |

At least one provider is required. More providers = better routing coverage. SearXNG needs no API key — just point `SEARXNG_BASE_URL` at your self-hosted instance.

You can also drop a `.env` file next to the server script:

```env
SERPER_API_KEY=xxx
TAVILY_API_KEY=xxx
EXA_API_KEY=xxx
QUERIT_API_KEY=xxx
PERPLEXITY_API_KEY=xxx
YOU_API_KEY=xxx
SEARXNG_BASE_URL=https://your-searxng-instance.example.com
```

## Tool Reference

### `web_search`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | *required* | Search query |
| `provider` | string | `"auto"` | Force provider: `auto`, `serper`, `tavily`, `exa`, `querit`, `perplexity`, `you`, `searxng` |
| `count` | integer | `5` | Number of results to return |

## Credits

Built on the **[web-search-plus](https://clawhub.com/skills/web-search-plus)** OpenClaw skill — a multi-provider search skill with intelligent auto-routing for AI assistants. The underlying `search.py` engine is extracted from that skill.

## License

MIT © 2026 robbyczgw-cla
