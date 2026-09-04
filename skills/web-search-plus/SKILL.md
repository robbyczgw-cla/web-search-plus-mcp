---
name: web-search-plus
description: >-
  Use the Web Search Plus MCP tools (web_search, web_extract) for source-backed
  web research: current events, prices, release notes, docs and API references,
  arXiv papers, CVEs, local and shopping queries, and reading a specific page.
  Use when the user mentions "web search plus", "websearchplus", "wsp",
  asks which sources say something, wants results from a named provider
  (Serper, Exa, Tavily, Linkup, You.com, Brave, Firecrawl, Parallel, SearXNG,
  Keenable), or asks to extract, read, or fetch a URL as markdown.
---

# Web Search Plus

Web Search Plus gives you two MCP tools. Both return sources, never answers.
You read the sources and synthesize; the server does not generate truth claims.

- `web_search` — multi-provider search with automatic routing. Returns ranked
  results with URL, title, snippet, provider, and routing metadata.
- `web_extract` — fetches one or more URLs and returns bounded markdown (or
  HTML), with optional query-ranked spans for long pages.

## When to prefer these over the built-in search

- The user wants to see **which sources** say something, or wants a
  quality/routing report.
- The query is provider-shaped: docs/API lookups, arXiv, CVE/security,
  GitHub/OSS discovery, local/shopping, news with a recency window.
- The user wants a **specific provider** or a **specific locale**.
- You need the **full text** of a page, not a snippet. Use `web_extract`.
- The user says "wsp", "web search plus", or names a provider.

For quick, one-line factual lookups the built-in search is fine. Do not run
both for the same question unless the user asks to compare.

## `web_search`

Required: `query`.

Useful parameters:

- `provider` — `auto` (default) or one of `serper`, `brave`, `tavily`,
  `linkup`, `exa`, `firecrawl`, `parallel`, `you`, `searxng`, `keenable`,
  `serpbase`, `querit`, `donsetch`, `octen`, `tinyfish`. Only providers with
  a configured key work; leave `auto` unless the user asks.
- `count` — results, default 5, max 20.
- `freshness` — `day`, `week`, `month`, `year` for recency.
- `search_type` — `news` for a news vertical.
- `country` / `language` — locale overrides.
- `include_domains` / `exclude_domains` — allow or deny lists.
- `mode` — `research` queries up to three providers concurrently, dedupes,
  and extracts the top sources. Slower and costs more; use for deep questions.
- `quality_report` — `true` to include routing class, provider scores, and
  authority signals. Useful when the user asks why a result ranked where it did.

Example:

```json
{ "query": "Hermes Agent 0.21 release notes", "freshness": "month", "count": 5 }
```

## `web_extract`

Required: `urls` (list).

Useful parameters:

- `provider` — `auto` (default) or `tavily`, `exa`, `linkup`, `parallel`,
  `firecrawl`, `you`, `keenable`, `serper`, `donsetch`.
- `format` — `markdown` (default) or `html`.
- `render_js` — `true` for JavaScript-heavy pages when the provider supports it.
- `spans` + `spans_query` — return the passages most relevant to a query instead
  of the whole page. Use this for long documents.

Extraction refuses private or internal targets (loopback, RFC1918, cloud
metadata hosts). That is deliberate; do not try to work around it.

Example:

```json
{ "urls": ["https://example.com/docs/setup"], "spans": true, "spans_query": "environment variables" }
```

## Working pattern

1. `web_search` with a precise query. Read the result list, not just the top hit.
2. `web_extract` the one or two URLs that actually answer the question.
3. Cite the URLs you used. Say when sources disagree.
4. If `web_search` returns an error that no provider is configured, tell the
   user to run `uvx --from web-search-plus-mcp==4.0.4 web-search-plus-mcp status`
   and set at least one provider key (see Setup). Do not guess results.

## Setup (first run)

The MCP server starts through `uvx`, so [uv](https://docs.astral.sh/uv/) must
be installed. Provider keys are read from the environment; the plugin ships none.

Recommended starter set: You.com + Serper + Linkup.

```bash
export YOU_API_KEY=...      # fast current and multilingual search
export SERPER_API_KEY=...   # Google-style facts, news, local, shopping
export LINKUP_API_KEY=...   # source-grounded results and clean extraction
```

Optional: `TAVILY_API_KEY`, `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `PARALLEL_API_KEY`,
`BRAVE_API_KEY`, `KEENABLE_API_KEY`, `SEARXNG_INSTANCE_URL`.

Check what is configured:

```bash
uvx --from web-search-plus-mcp==4.0.4 web-search-plus-mcp status
```

Write a starter `.env` template:

```bash
uvx --from web-search-plus-mcp==4.0.4 web-search-plus-mcp setup --preset starter
```

Full provider list, routing rules, and tool reference:
https://github.com/robbyczgw-cla/web-search-plus-mcp
