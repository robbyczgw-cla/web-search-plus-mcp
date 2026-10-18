# web-search-plus-mcp 5.1.2

Released 2026-10-18. 5.1.1 was never released, so these notes cover everything since 5.0.1.

Matches the engine of Hermes Web Search Plus 5.1.2 (the 5.1.1 engine, which includes the engine parts of 5.1.0, plus the two extract fixes below). Bug fixes for 5.0.1 and one additive output field; no breaking changes, tool names, input schemas, routing defaults and config format stay the same.

## Fixed

- **No provider request after the request deadline.** The deadline now reaches every provider call, batch loop and retry. Pages already fetched are kept; the rest of a batch is marked `not tried: request ran out of time`. Octen, TinyFish and DonSeTch respect the per-attempt timeout cap, and `research` passes its deadline to its members and its source extraction.
- **Running out of time is not a provider failure.** It opens no circuit, records no latency sample and uses no budget unit when nothing was sent.
- **Brave's per-second 429 retry lives in the attempt engine**, so it respects the deadline and shows up as its own try in receipts.
- **Request budget without SQLite.** The per-request attempt limit is enforced even when the state store is unavailable; a daily limit fails closed when the ledger cannot be read; SQLite is probed again 30 s after an I/O error.
- **Half-open probes release their lease** when they end without a verdict on the provider or are blocked by a budget, so a provider is no longer blocked for 60 s by a probe that never ran.
- **One result per requested URL in `web_extract`,** in request order, also when several providers served the batch. Rewritten URLs (`http` → `https`, redirects, trailing slash, IDN) are matched to the URL you asked for; an item that cannot be matched leaves the URL open for fallback.
- **A rate limit, out-of-credit or auth error partway through a `web_extract` batch no longer throws away the pages already fetched.** Firecrawl, Linkup, Serper and Keenable stop the batch at the first provider-wide error, keep the fetched pages and mark the URL that failed and the URLs not yet tried with the cause, for example `not tried: provider rate limit reached` (also `provider out of credits`, `provider authentication failed`, `provider configuration error`). Only those URLs go to the next provider. The attempt is reported as `partial`, keeps the error in its receipt and opens the circuit, so automatic routing backs off; the batch is never retried at the same provider, which would pay again for fetched pages. Partial results are not cached. If the error comes on the first URL, the attempt fails as before. Serper and Keenable now report these errors to the circuit breaker (a 429 used to become a per-URL error on every URL). When the DonSeTch session fails partway through a batch, the pages already fetched are kept.
- **URLs past the per-call limit get their own row.** `web_extract` processes at most `bounded_context.max_urls` URLs per call (default 10). The rest used to vanish from `results` with only a note in `limits_applied`; each now comes back as `{"url": …, "requested_url": …, "content": "", "error": "not tried: limit of 10 URLs per call reached"}`, in request order. Send them in another call.
- **The search cache is keyed by the credentials that produced a result.** A new key or SearXNG instance no longer returns cached results of the old one.
- Brave queries are shortened only past 600 characters / 75 words.
- A `jev.api_key` in `config.json` is ignored with a warning instead of discarding the whole config file.
- Provider names given to `web_extract` are matched case-insensitively in the engine; unknown names return a clean error.

## Compatibility

- `web_search` and `web_extract` names and input schemas are unchanged.
- Additive: every `web_extract` result carries `requested_url`, the URL you passed in. `url` is unchanged and stays the URL the page was fetched from (after redirects and normalization), so two inputs such as `https://example.com/?ref=a` and `?ref=b` can share one `url` but are told apart by `requested_url`. Results are still one per requested URL in request order; `requested_url` lets clients match them without relying on order. It is a field of the MCP projection only: the canonical v3 response and `schemas/v3` are unchanged.
- Additive: a `partial` provider attempt can carry `error` next to its results when a provider-wide error stopped a batch.
- Additive: the `wsp.extract.partial` warning may carry `details.unmatched_count`, and extract payloads may carry `unmatched_results`; `details.failed_urls` stays.
- Provider SDK: `wsp_sdk` additionally exports `RequestDeadlineExceeded`, `deadline_passed`, `dispatch_timeout` and `remaining_seconds`.
- New module `web_search_plus_mcp.credentials`. No secret resolver is installed in this package, so keys still come from the MCP client `env` block, the process environment and the `.env` files the server loads.

## Not ported

Hermes plugin-only changes: profile-scoped provider keys (plugin catalog rule 11) and the removal of `.env` loading, the removal of `TYPESAFE_API_KEY_FILE`, `hermes web-search-plus` commands, Hermes Desktop settings, and the native backend with its keyless-rescue handling. The Hermes plugin's text formatter for extract results has no counterpart here; the MCP projection adds the over-limit rows itself.
