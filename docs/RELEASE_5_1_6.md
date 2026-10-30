# web-search-plus-mcp 5.1.6

Released 2026-10-30. Honest page extraction, the same engine changes as the Hermes plugin 5.1.7.

## Fixed

- **Failed extractions say why.** Before, an MCP client got `results: []` and "Provider returned an invalid response" for a page that does not exist. Now: `"error": "Could not read the page: page not found (HTTP 404)"` and one row per URL with its reason (not found, removed, site refused, unreachable, provider does not support the site).
- **A missing page costs one call** instead of three paid fallback calls.
- **Fallback reaches three providers again** after a transient error.
- **Firecrawl:** a 404 page is an error instead of cached content, and a site Firecrawl does not support no longer blocks Firecrawl for five minutes for every URL.

## Checked before release

- Installed wheel in an empty environment, real MCP stdio client, real keys: a missing page returns `isError: true` with the reason after one Tavily call; a batch of a page and a missing page returns the page and the reason (status `degraded`); `provider: "firecrawl"` on a site it refuses says so, and the next Firecrawl request works.
- Provider answers recorded on 2026-10-30 drive `tests/test_extract_failure_reasons.py`; all 7 tests fail on 5.1.5.
- The full v3 response of a failed extract validates against `schemas/v3/response.schema.json`.
