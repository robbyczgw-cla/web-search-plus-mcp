# web-search-plus-mcp 5.1.7

Released 2026-11-08. `status`, setup guidance and tool errors agree with the engine on whether a provider can run, and say why not. Same engine changes as the Hermes plugin 5.1.8.

## Fixed

- **Status tells the truth.** Placeholders and private SearXNG URLs no longer show as configured; config.json keys, keyless opt-ins and `$HERMES_HOME/.env` keys no longer show as missing. Each provider gets `state`, `reason_code`, `reason`, `fix` and `source`.
- **Placeholders no longer hide real keys** from `$HERMES_HOME/.env`.
- **Errors name the setup problem** (placeholder key, private SearXNG URL, disabled provider) with the fix, instead of "Missing API key for serper" and Serper signup steps.
- **`WEB_SEARCH_PLUS_MCP_DETAIL`** empty or in another case no longer breaks every tool call.
- **DonSeTch:** config.json `donsetch.binary` works.
- **Config CLI** validates edits with the engine's rules and never leaves a file the engine will move aside; `set-default` changes the provider actually used.
- **Research returns the pages it read** (full: bounded text; compact: short excerpts) and names failed reads.
- **Research status is stable** and `fallback_reason` is consistent; **state store** no longer shows healthy providers as open and reclaims reservations of crashed processes; **DonSeTch** errors keep their class.

## Checked before release

- `tests/test_mcp_readiness.py` starts fresh interpreters on a copy of the package with real `.env` files and checks status against the engine; all of its tests fail on 5.1.6.
- Built wheel in an empty environment: `status --json` with a placeholder Brave key and a config.json keyless opt-in reports Brave `invalid_value` and Keenable `ready`; a real MCP stdio client with an empty `WEB_SEARCH_PLUS_MCP_DETAIL` gets a normal answer that names the placeholder.
- The full v3 response of a setup failure validates against `schemas/v3/response.schema.json`.
