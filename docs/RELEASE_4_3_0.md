# Web Search Plus MCP 4.3.0

Same public version as Hermes Web Search Plus 4.3.0. MCP tool names, arguments, and legacy result fields stay the same.

Pin `web-search-plus-mcp==4.3.0` in `uvx` and Agent Plugins manifests.

```bash
uvx --from web-search-plus-mcp==4.3.0 web-search-plus-mcp status
```

## Adaptive routing learns again

Since the 3.0 attempt engine, searches that the engine runs had stopped recording results. Adaptive routing received no new samples and fell back to static priority. Every real provider call now records latency, result count, and error. This includes each research member and each retry. Cache hits and config errors still record nothing.

`provider_stats.json` writes now take a file lock (POSIX). Before, two processes writing at the same time overwrote each other and lost up to half of the samples.

## `max_results` applies again

`web_search` no longer forces `--max-results 5` when the client omits `count`, so `defaults.max_results` in `config.json` applies. `count: null` no longer produces `--max-results None`, which the search script rejected. An explicit `count` still wins.

The Hermes Desktop settings form from Hermes Web Search Plus 4.3.0 is Hermes-plugin-only.
