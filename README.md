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

| Provider | Best For | Required Key |
|----------|----------|-------------|
| **Serper** (Google) | General search, news, current events | `SERPER_API_KEY` |
| **Tavily** | Research, deep content extraction | `TAVILY_API_KEY` |
| **Exa** | Neural / semantic / discovery search | `EXA_API_KEY` |

Auto-routing picks Serper for news/general queries, Tavily for research/analysis, and Exa for discovery-style or semantic queries. Falls back gracefully if a provider key is missing.

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
        "EXA_API_KEY": "your_exa_key"
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
        "EXA_API_KEY": "your_exa_key"
      }
    }
  ]
}
```

## API Keys

| Provider | Free Tier | Get Key |
|----------|-----------|---------|
| Serper | 2,500 free searches/month | [serper.dev](https://serper.dev) |
| Tavily | 1,000 free searches/month | [tavily.com](https://tavily.com) |
| Exa | 1,000 free searches/month | [exa.ai](https://exa.ai) |

At least one provider key is required. All three recommended for best routing.

You can also drop a `.env` file next to the server script:

```env
SERPER_API_KEY=xxx
TAVILY_API_KEY=xxx
EXA_API_KEY=xxx
```

## Tool Reference

### `web_search`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | *required* | Search query |
| `provider` | string | `"auto"` | Force provider: `auto`, `serper`, `tavily`, `exa` |
| `count` | integer | `5` | Number of results to return |

## Credits

Built on the **[web-search-plus](https://clawhub.com/skills/web-search-plus)** OpenClaw skill — a multi-provider search skill with intelligent auto-routing for AI assistants. The underlying `search.py` engine is extracted from that skill.

## License

MIT © 2026 robbyczgw-cla
