# Migrating web-search-plus-mcp 0.x to 1.0

`web-search-plus-mcp` 1.0 aligns the standalone MCP package with the source-only Web Search Plus 3.0.2 engine. The MCP transport remains stdio and the public tool names remain `web_search` and `web_extract`.

## Before upgrading

1. Back up your MCP host configuration, provider `.env`, and `config.json`.
2. Check the current provider configuration:

```bash
web-search-plus-mcp status --json
web-search-plus-mcp config show
```

3. Upgrade the package:

```bash
pip install --upgrade web-search-plus-mcp
# or let uvx resolve 1.0 on the next launch
uvx web-search-plus-mcp
```

4. Restart or reconnect the MCP host so it refreshes the tool schemas.

## Breaking provider change

Native `perplexity` and `kilo-perplexity` are no longer public search providers. Their available endpoints return synthesized answers and do not expose a verified source-only mode, so 1.0 refuses to present them as search.

- They are absent from the `web_search.provider` enum.
- Direct low-level calls using either retired ID return the typed error `wsp.provider.source_only_required` without dispatching a provider process.
- Retired IDs in provider priority, disabled-provider, or `auto_allow` lists are ignored when old config is loaded.
- A retired default or fallback provider is replaced in memory with `serper` and reported through a config migration warning.
- Loading old config does not silently rewrite the file. Review the warning, then save an explicit 1.0 configuration with the CLI if desired.

Use one of the 12 source-result providers instead. Guarded providers can be opted into automatic routing explicitly:

```bash
web-search-plus-mcp config set-fallback serper
web-search-plus-mcp config set-auto-allow parallel on
web-search-plus-mcp config set-priority serper,brave,tavily,linkup,you,exa,firecrawl,parallel
```

## Response compatibility

The established MCP tool names and legacy result fields remain available:

- Search: `provider`, `query`, `results[]` with `title`, `url`, and `snippet`
- Extract: `provider`, `urls`, `results[]` with `url` and `content`
- Failures: the legacy string `error` remains present where applicable

The 1.0 response adds the Web Search Plus v3 evidence contract:

- `contract_version`, `request_id`, `execution_id`, and typed `status`
- lossless `observations` and result-to-observation provenance
- `provider_attempts`, retries/skips, and `routing_receipt`
- `cache_status` and cache-origin evidence
- `limits_applied`, `stored_content`, truncation warnings, and page-on-demand references
- typed `error_v3`

These fields are additive. Clients that ignore unknown fields can continue consuming the legacy projection; clients that validate closed response objects must update their schemas.

## Extraction behavior

Extraction remains capped at 10 URLs per call. Long content is bounded deterministically, while the full cleaned text is stored locally and referenced through `stored_content`. Private and internal target URLs remain blocked before provider dispatch unless the operator explicitly enables trusted private extraction.

## MCP-specific scope

The standalone server deliberately does not port Hermes-only surfaces:

- Hermes plugin lazy loading and the 3.0.1 in-process import-precedence hotfix
- Hermes setup/fastpath commands
- the local Operator Console
- Hermes plugin release metadata

The MCP process continues to execute the engine behind its stdio/subprocess boundary.

## Rollback

If a client cannot yet accept the 1.0 provider/schema changes, pin the previous package temporarily:

```bash
pip install "web-search-plus-mcp==0.17.0"
# or
uvx --from "web-search-plus-mcp==0.17.0" web-search-plus-mcp
```

Do not keep retired answer providers in new integrations. The rollback is a compatibility bridge, not a long-term source-only path.
