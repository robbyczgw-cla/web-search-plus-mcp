# web-search-plus-mcp 4.3.1

Performance release matching Hermes Web Search Plus 4.3.1. No tool schema changes.

- `web_search` and `web_extract` run the search engine inside the MCP server instead of spawning `search.py` per call. Same arguments, parser, and per-call config reload; error and timeout payloads are unchanged. `WSP_FORCE_SUBPROCESS=1` restores one process per call.
- Provider HTTP calls reuse keep-alive connections per host. Proxies and `WSP_HTTP_KEEPALIVE=0` keep plain `urlopen`.

Live stdio medians with real keys: auto routing 1.70 s → 0.99 s (−42 %), Serper −18 %, Tavily −4 %, Exa unchanged.

**Note:** `.env` is now read once at server start. Restart the MCP server after adding a key there. `config.json` is still read per call.
