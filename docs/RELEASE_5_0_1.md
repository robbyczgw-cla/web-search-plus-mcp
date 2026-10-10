# web-search-plus-mcp 5.0.1

Matches Hermes Web Search Plus [v5.0.1](https://github.com/robbyczgw-cla/hermes-web-search-plus/releases/tag/v5.0.1). Bug fixes for 5.0.0; no breaking changes, routing, providers and config format stay the same.

## Fixed

- **Normal queries no longer trip the source-only filter.** Searches with words such as "synthesizer" or "verify the claim" failed at Exa, Tavily and Linkup, and docs queries meant for Exa fell through to another provider. The filter now checks only what Web Search Plus itself sends, not your query, URLs or domain filters.
- **One bad URL no longer sinks a `web_extract` batch.** Each blocked, unresolvable or failing URL gets its own `error` in `results[]` (also listed in the `wsp.extract.partial` warning under `details.failed_urls`); the other URLs are still extracted, and failed ones are retried on the next extraction provider. Error messages no longer reveal internal IP addresses.
- **Empty pages are no longer a success.** Blank extractions fall back to the next provider and are not cached.
- **Bounded rate-limit waits.** A long `Retry-After` is not waited out inline (cap 30 s); retries without one back off briefly; malformed values no longer crash the attempt.
- **Long queries work at Brave.** Queries are shortened at a word boundary to Brave's 400 characters / 50 words, `site:` operators kept, instead of being rejected. A provider rejecting a too-long query reads "Query rejected … it may be too long".
- **Auto routing off without a default provider** uses the configured provider order instead of failing every search.
- **A private SearXNG URL** without `SEARXNG_ALLOW_PRIVATE=1` skips SearXNG instead of breaking every automatic search.

## Compatibility

- `web_extract` results for failed URLs now carry an `error` string next to the empty `content`.
- The `wsp.extract.partial` warning adds `details.failed_urls` (`url`, `error`); `failed_count` is unchanged.
