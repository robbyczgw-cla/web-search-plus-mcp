# web-search-plus-mcp 1.2 release notes

Version 1.2 packages the portable Web Search Plus 3.2 provider contract for MCP
clients and adds Hound as an optional local Search and Extract provider.

## Highlights

- 13 source-result Search providers and 9 Extract providers
- optional local Hound sidecar through MCP Streamable HTTP
- Hound remains explicit-only until `auto_allow` is enabled
- loopback-only endpoint validation with no redirects or proxy inheritance
- Hound response caching disabled so Web Search Plus retains cache ownership
- full Hound Search and Extract projection through the existing two MCP tools
- `mcp>=1.26,<2` and explicit `httpx>=0.27,<1` runtime dependencies

## Stable public surface

The server still exposes exactly two tools:

- `web_search`
- `web_extract`

Hound is additive in both provider enums. Existing tool names, source-only
contracts, typed errors, evidence receipts, bounded extraction, and legacy
result fields remain stable.

## Hound operation

Hound is installed and run separately. It is not embedded in the wheel. The
adapter accepts only literal loopback endpoints such as:

```text
http://127.0.0.1:8765/mcp
http://[::1]:8765/mcp
```

See [HOUND.md](HOUND.md) for installation, configuration, keyless trade-offs,
security boundaries, and opt-in automatic routing.

## Attribution

[Hound / Master Fetch](https://github.com/dondai1234/master-fetch) is an
independent MIT-licensed project created and maintained by
[Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234). Web Search Plus
connects to it as a separately installed sidecar; it does not vendor or fork the
project.

The Hound integration was validated against `hound-mcp 11.1.6`.

## Upgrade

```bash
pip install --upgrade "web-search-plus-mcp==1.2.0"
```

Or pin the version in an MCP host configuration:

```json
{
  "command": "uvx",
  "args": ["web-search-plus-mcp==1.2.0"]
}
```

No migration is required for users who do not configure Hound.
