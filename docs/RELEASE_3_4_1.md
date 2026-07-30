# web-search-plus-mcp 3.4.1 release notes

`web-search-plus-mcp 3.4.1` packages the portable Web Search Plus v3.4.1 engine for MCP clients. It adds Exa freshness bounds and one optional source-search provider without changing the stable two-tool MCP surface.

## Highlights

- add native Exa freshness support by converting `day`, `week`, `month`, and `year` into absolute UTC publication-date bounds;
- add TinyFish as an explicit-only, BYOK-only source-search provider;
- keep TinyFish outside automatic routing and fallback (`auto_allow=false`);
- preserve the 9-provider extraction surface and stable `web_search` / `web_extract` tools.

## TinyFish source search

Configure your own `TINYFISH_API_KEY`, then request TinyFish explicitly:

```json
{
  "query": "recent retrieval research",
  "provider": "tinyfish",
  "freshness": "month"
}
```

Web Search Plus MCP does not provide, pool, proxy, or share TinyFish credentials. The adapter calls only the fixed official HTTPS Search API origin, rejects redirects, and does not use TinyFish Browser, Agent, Fetch, or optional purpose paths. Query, domain, URL, response, and aggregate-size bounds fail closed, and upstream errors remain opaque.

## Privacy and Terms warning

Review the official [TinyFish Search API reference](https://docs.tinyfish.ai/search-api/reference) and [TinyFish Terms](https://www.tinyfish.ai/terms) before use. The published standard Terms grant broad rights over Customer Data, including queries, for analysis, training, fine-tuning, evaluation, and model improvement. No binding Search-specific no-training exclusion or fixed deletion period is claimed here. Treat TinyFish as **high risk** and complete your own legal review before sending sensitive queries.

Explicit-only routing limits accidental selection; it is not a privacy guarantee.

## Exa freshness

Unified freshness now applies to Exa by generating absolute UTC `startPublishedDate` and `endPublishedDate` values. Explicit `start_date` and `end_date` arguments still take precedence.

Freshness metadata reports those effective explicit overrides, including mixed cases where only one boundary is supplied.

This behavior originated in [Web Search Plus #111](https://github.com/robbyczgw-cla/hermes-web-search-plus/pull/111) by [@kesku](https://github.com/kesku).

## Stable MCP surface

The server still exposes exactly two tools:

- `web_search`
- `web_extract`

Existing installations behave as before unless an operator adds `TINYFISH_API_KEY` and explicitly requests `provider="tinyfish"`, deliberately opts TinyFish into automatic routing, or sends a unified freshness value to Exa.

## Hound / Master-Fetch attribution

[Hound / Master-Fetch](https://github.com/dondai1234/master-fetch) remains an independent MIT-licensed project created and maintained by [Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234). Web Search Plus MCP ships only its own client adapter and connects to a separately installed loopback Hound sidecar; Hound is not bundled, forked, or claimed as Robby's code.

## Upgrade

```bash
pip install --upgrade "web-search-plus-mcp==3.4.1"
```

Or pin the version in an MCP host configuration:

```json
{
  "command": "uvx",
  "args": ["web-search-plus-mcp==3.4.1"]
}
```
