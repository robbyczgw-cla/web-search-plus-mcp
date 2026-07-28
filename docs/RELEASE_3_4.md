# web-search-plus-mcp 3.4 release notes

`web-search-plus-mcp 3.4.0` packages the portable Web Search Plus v3.4.0 engine for MCP clients. It adds one optional source-search provider without changing the stable two-tool MCP surface.

## Highlights

- add Octen source search through Monid's documented HTTP API;
- keep Octen explicit-only by default (`auto_allow=false`), outside automatic routing and fallback;
- support native recency plus include/exclude-domain filters;
- return ranked source links and highlights while disabling full-content retrieval;
- report Provider SDK freshness support truthfully for discovered search providers.

## Octen via Monid

Octen supplies the search results. Monid provides API access and billing. Configure a `MONID_API_KEY` from [Monid](https://app.monid.ai/access/api-keys), ensure the Monid wallet has balance, and request Octen explicitly:

```json
{
  "query": "recent vector database research",
  "provider": "octen",
  "freshness": "month"
}
```

Access and billing use Monid's prepaid wallet; see Monid for current pricing and terms. Web Search Plus makes no free-tier, price, latency, quality, availability, partnership, or endorsement claim for Octen or Monid.

## Security and scope

The adapter sends credentials only to Monid's fixed HTTPS API origin, rejects redirects, caps response bodies at 8 MiB, and sanitizes upstream failures. Octen answer, Broad Search, image/video, and full-content modes remain outside this source-only integration.

## Stable MCP surface

The server still exposes exactly two tools:

- `web_search`
- `web_extract`

Their names, arguments, and legacy result fields remain compatible. No configuration migration is required. Existing installations behave as before unless an operator adds `MONID_API_KEY` and explicitly requests `provider="octen"` or deliberately opts Octen into automatic routing.

## Hound / Master-Fetch attribution

[Hound / Master-Fetch](https://github.com/dondai1234/master-fetch) remains an independent MIT-licensed project created and maintained by [Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234). Web Search Plus MCP ships only its own client adapter and connects to a separately installed loopback Hound sidecar; Hound is not bundled, forked, or claimed as Robby's code.

## Upgrade

```bash
pip install --upgrade "web-search-plus-mcp==3.4.0"
```

Or pin the version in an MCP host configuration:

```json
{
  "command": "uvx",
  "args": ["web-search-plus-mcp==3.4.0"]
}
```
