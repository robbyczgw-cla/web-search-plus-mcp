# web-search-plus-mcp 5.1.9

Released 2026-11-25. Same engine changes as the Hermes plugin 5.1.10.

## Fixed

- **UTF-8 everywhere.** On Windows, and on any system with a non-UTF-8 locale, a valid `config.json` holding a character such as `ü` or `”` was reported invalid and every setting fell back to the default; a file with a BOM did the same, and `setup` could fail on a cp1252 console. `config.json`, `.env` and the CLI output now use UTF-8 (a BOM is accepted); damaged bytes still move the file aside instead of being silently replaced. Same engine change as hermes-web-search-plus #175 by @pompousman.
- **Help and docs match the routing.** `search.py --help` and the docs still named Serper for shopping (Brave since 5.1.6), and the migration guide suggested changing the priority to opt a provider in (`config set-auto-allow <provider> on` is enough since 5.1.8).

## Added

- **Search endpoints for Brave, Tavily and Exa** can be overridden in `config.json` (`brave.api_url`, `tavily.search_url`, `exa.base_url`), like the existing endpoint overrides, for example to use a compatible proxy or multi-key gateway. Defaults are unchanged. Thanks to @hardworkDAD (#71).

## Checked before release

- Each fix has a test that fails without it; full suite green with the default locale and with `LC_ALL=C PYTHONUTF8=0`.
- Independent test runs with a real MCP stdio client: UTF-8 configs and endpoint overrides against a local server, and on a separate installation a real search, research call and 404 extract.
