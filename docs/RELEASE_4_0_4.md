# Web Search Plus 4.0.4

## Fixed

- Preserve queries such as `--help` and `-site:reddit.com` as search text through structured requests and subprocess adapters. Apply the same treatment to `spans_query`.
- Reject malformed section shapes in the shared budget-preflight helper.

## Maintenance

- Share daily-budget settings and adapter-signature validation while retaining both enforcement boundaries.
- Replace prose-only compatibility assertions with checks of real exports and defensive copies. Remove the nonexistent `search_provider` entry from the compatibility inventory, not an implementation.
- Remove empty section headers and the pass-through contract-error factory.

No provider, tool-schema, or configuration migration is required.

## MCP packaging

Includes the previously merged Grok Build plugin packaging: `.mcp.json`, the search skill, and `.grok-plugin/plugin.json`. Install pins now select 4.0.4. The source-only `web_search` and `web_extract` tools and both supported MCP protocol generations remain unchanged.
