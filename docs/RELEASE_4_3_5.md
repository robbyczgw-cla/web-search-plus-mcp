# web-search-plus-mcp 4.3.5

Matches Hermes Web Search Plus 4.3.5.

## Fixed

- **Missing-key hints reach the client.** 4.3.4 generated setup hints, but the v3 error classification replaced them with `Provider configuration is invalid` before they reached the MCP client. A missing key now returns `Missing API key for <provider>` with `error_v3.details.env_var`, `how_to_fix` and `setup_required`. Only WSP's own guidance in its exact shape is passed through; other configuration error text stays redacted.
- **`isError` for failed calls.** A failed `web_search` or `web_extract` now sets `isError: true`. Before, the client got `isError: false` and the failure only inside the JSON text.
- **`web_extract` without a key** returns the same setup guidance as `web_search`.
- **Locale is applied.** The built-in config no longer ships `country`/`language` for Brave, You.com, Firecrawl, SerpBase and SearXNG. Those values were read as explicit user settings, so a German query with locale `at` reached Brave as `US`/`en`. Your own `country`/`language` settings still win.
- **Dedup keeps different pages apart.** `youtube.com/watch?v=A` and `?v=B` were merged into one result. Only tracking parameters are removed now.
- **`web_extract` respects its size limit.** The full page was repeated in `observations[].text`, so a 105k-character page returned 168 KB. `observations[].text` is now `null` for extract; the bounded text stays in `results[].content`, the full page in `stored_content`.

## Compatibility

- `observations[].text` is `null` in `web_extract` responses.
- `error_v3.details` may be non-empty for configuration errors. `code` and `error_class` are unchanged.
- Clients that treated every tool call as a success may now see `isError: true` for failures.
