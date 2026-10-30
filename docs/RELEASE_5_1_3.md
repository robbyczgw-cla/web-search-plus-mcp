# web-search-plus-mcp 5.1.3

Released 2026-10-30.

## Changed

`web_search` and `web_extract` now return compact JSON by default, as one `TextContent`. Search no longer repeats its sources in observations, policy actions and dedup clusters or sends the complete execution diagnostics on every call. Source titles, URLs, snippets and bounded extracted text are unchanged between modes.

Both tools accept `detail: "compact" | "full"`. **Clients parsing the full v3 contract, including observations or routing receipts, must pass `detail: "full"` or configure that server default.** Full mode preserves the 5.1.2 projection, including the requested quality report. The compact default affects the MCP response only. This release also carries the Hermes 5.1.6 engine fixes described below; tool names, existing argument names and extraction limits remain unchanged.

## Engine fixes from Hermes 5.1.6

Ported from upstream commits `faa0110`, `2b7e544` and `1eb9b8c`:

- Google `/goto` wrappers are dropped without Google requests by default. Classic `/url?q=` wrappers decode locally. Set `{"serper": {"resolve_redirects": true}}` in config.json to opt into bounded, one-hop resolution with request deadlines and URL safety checks.
- SerpBase uses `device=mobile` by default; `serpbase.device` accepts `mobile` or `desktop`. Canonical `url` takes precedence over `link`; `source_url` is provenance only. Requests use the WSP user agent.
- A shared URL sanity filter removes control characters, replacement characters and narrowly identified encoding damage before ranking, observations and caches, retaining legitimate Unicode URLs.
- Security and shopping now start with Brave, with Serper later in the fallback order, matching Hermes routing tables.
- DonSeTch 4.10.3 is the tested version; see [DONSETCH.md](DONSETCH.md).

Redirect and invalid-URL counts survive fallback, Research and cache hits. Compact output includes `redirects_wrapped`, `redirects_resolved`, `redirects_dropped` and `invalid_urls_dropped` only when positive. Full mode keeps all receipt details, including zero redirect counts. Cache identities separate the URL-cleaning policy, resolver setting and SerpBase device from older entries.

Hermes text-header formatting and Hermes-only size tests are not applicable to this stdio MCP server. An MCP projection test covers the new metadata under the existing ≤30% / <6 KB budget (4,032 compact bytes versus 15,418 full bytes, 26.15%, for the eight-source fixture).

## Server default

Selection order: tool argument > `WEB_SEARCH_PLUS_MCP_DETAIL` > `mcp.detail` in the existing config file > `compact`. Values must be exactly `compact` or `full`. Clients can omit the argument to inherit the server setting.

For clients unable to pass new arguments, set `WEB_SEARCH_PLUS_MCP_DETAIL=full` in their MCP server `env` block or process environment. Alternatively, add `{"mcp": {"detail": "full"}}` to config.json; `WEB_SEARCH_PLUS_CONFIG` selects a custom path. Existing config commands preserve this section.

## Compact response

- Search keeps title, URL, snippet, publication date when present, and short source-type/fetch-priority labels. It includes a small routing summary, cache hit/age, and research providers merged. A research page count is included only if extraction receipts provide it; the current canonical search contract can omit this information.
- Extract keeps one result per requested URL, including redirects, errors and omitted URLs. Each row keeps URL, requested URL, title, bounded content, requested spans and any full-text storage reference, length and checksum. Storage failure is explicit. Unbounded observation text never crosses the compact boundary.
- Warnings and provider failure reasons are short strings. Failures keep `status: "failed"`, the error, setup instructions and environment-variable names. MCP `isError` still works in both modes.
- Compact output has `detail: "compact"` and a one-line hint for requesting `full`; `contract_version` is reserved for full output. Request `detail: "full"` with `quality_report: true` for detailed diagnostics.

## Verification

Offline tests pin serialized full search, research, extract and failure projections from v5.1.2 (`7a8bd57`). The eight-result search fixture uses ordinary 270-character snippets from the runtime's observation/result builder: compact output must remain at most 30% of full and below 6 KB. The absolute cap permits the fixture's source text and small summaries while detecting accidental repeated evidence; it is a regression budget, not a cap that truncates search results.

Live stdio check on 2026-10-30, with the environment loaded via `uv run --env-file` and Serper selected explicitly: `Football Manager 27 skins modding`, count 8, and extraction of `https://example.com`. Both tools succeeded in both modes, without cache hits. An isolated configuration disabled other providers and capped attempts at one per call: four provider calls total. No credentials were printed or saved in release artifacts.

| Tool | Compact bytes | Full bytes | Approx. tokens compact / full |
| --- | ---: | ---: | ---: |
| Search, 8 results | 3,740 | 19,049 | 935 / 4,762 |
| Extract, 1 URL | 493 | 2,852 | 123 / 713 |

Token estimates use UTF-8 bytes / 4, not a tokenizer. These are separate live requests: the search result sets varied (three shared URLs, with identical titles/snippets on those URLs), so the size reduction is indicative. Reprojecting the same full search response offline yields 3,600 compact bytes. Extract content matched exactly. Offline fixtures and in-process boundary tests establish source-text equality for identical engine responses; no additional live calls were made.


Engine-port live check on 2026-10-30: one stdio server process, two uncached compact calls, environment loaded with `uv run --no-sync --env-file` and no credentials printed or saved. An isolated config allowed only Brave and Serper and capped provider calls at one per request.

| Query / requested provider | Serving provider | Sources | Compact bytes | redirects_dropped |
| --- | --- | ---: | ---: | ---: |
| Football Manager 27 skins modding / serper | serper | 3 | 1,502 | 7 |
| openssl CVE-2026 vulnerability / auto | brave | 8 | 6,301 | 0 (omitted) |

Serper returned Passion4FM, Reddit and Instagram URLs; no `google.com/goto` URL remained. The automatic security search returned OpenSSL's vulnerability page and seven other sources. Seven wrappers were counted, zero resolved and seven dropped on Serper; Brave returned no wrappers. Byte sizes measure the UTF-8 MCP `TextContent.text` JSON. The Brave response exceeds the fixed fixture's 6-KB regression budget because its live snippets are longer; that budget is not an output truncation limit. Hermes-only text headers and output-size tests were deliberately omitted; the MCP metadata size regression covers this package's output boundary.
