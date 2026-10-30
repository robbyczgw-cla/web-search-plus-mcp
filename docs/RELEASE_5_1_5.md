# web-search-plus-mcp 5.1.5

Released 2026-10-30. Bug-fix release found by a code review of 5.1.4; no output format changes.

## Fixed

- **DonSeTch:** explicit `provider: "donsetch"` searches failed with DonSeTch 4.7.1 and newer ("Provider execution failed"). The adapter is now the same as in the Hermes plugin 5.1.6 (split result shape, `[meta]` fallback, Windows-safe reader).
- **Subprocess mode:** `WSP_FORCE_SUBPROCESS=1` and the fallback when the in-process engine cannot load returned "Web Search Plus subprocess failed." for every call. `search.py` now runs as a module.
- **Config file:** a tool call could rename a valid config (`"extract_provider_priority": []`) to `config.json.broken-*` and then search without your `disabled_providers`. Read paths no longer move files.

## Checked before release

- Installed wheel in an empty environment, real MCP stdio client, DonSeTch 4.10.3: search (5 results) and extract (2 pages), in-process and with `WSP_FORCE_SUBPROCESS=1`.
- The same with published 5.1.4: "Provider execution failed".
- Claude Code (real client) with the built package: DonSeTch search returned the three expected Python 3.14 release-notes URLs.
- Auto search with real keys and a config that disables Serper: served by Brave, 4.3 KB compact, config file unchanged.
- Windows: covered by a test that reads replies without `select`; not run on a real Windows machine.
