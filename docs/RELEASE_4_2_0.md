# Web Search Plus MCP 4.2.0

Same public version as Hermes Web Search Plus 4.2.0. MCP tool names, arguments, and legacy result fields stay the same.

## Optional Jev

TypeSafe System One is available and **off by default**. It is not a search provider.

```bash
uvx --from web-search-plus-mcp==4.2.0 web-search-plus-mcp setup --preset starter \
  --jev --jev-key-file /path/to/typesafe_api_key
```

`--no-jev` leaves it disabled. The TypeSafe key is stored as `TYPESAFE_API_KEY_FILE` and is never written to `config.json`.

When enabled, three decisions can run:

1. **search_type overlay** — Keyword heuristics may propose `news`. Jev confirms only at confidence ≥ 0.95. Otherwise the request stays `search`. Explicit `search_type=news` is not overridden. WSP still exposes only `search|news`.
2. **extract_quality** — After extract, Jev may keep a long page that regex treated as a bot wall, or reject chrome, if confidence ≥ `jev.min_confidence` (default 0.85).
3. **language_fill** — Only when WSP language inference returned none.

Missing SDK, missing key, timeout, or low confidence leaves WSP behavior unchanged.

The opt-in Hermes native `wsp` backend remains Hermes-plugin-only. DonSeTch stays a separately installed upstream project.

## Upgrade

Pin `web-search-plus-mcp==4.2.0` in `uvx` and Agent Plugins manifests.
