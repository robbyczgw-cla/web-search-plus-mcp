# web-search-plus-mcp 5.1.8

Released 2026-11-10. Settings mean what they say: what `status`, setup and tool errors tell you is what the engine does, and every command they suggest works. Same engine changes as the Hermes plugin 5.1.9.

## Fixed

- **One `starter` preset.** The setup error named Serper, Brave, Linkup and Exa, but `setup --preset starter` wrote You.com, Serper and Linkup. There is now one preset table: `starter`, `lean`, `search`, `extract`, `all` (`minimal` still works as an alias for `lean`), and the config snippet names the keys of the chosen preset.
- **Suggested commands work.** Status and errors suggested `setup brave` and `setup --preset extract`, which the CLI rejected; they now name the env var to set or a preset that exists.
- **Status shows what the engine runs with.** Under `profile: self_hosted` it listed brave/serper; with `provider_priority: []` the full default list; a config.json the engine rejects had no warning until the first search moved it aside. Status and `config show` now use the engine's view and warn first.
- **Status says when no provider runs automatically** (only explicit-only or disabled providers), and names template placeholder keys.
- **`config set-auto-allow X on` is enough** to add a provider to automatic search; the hint no longer suggests `set-priority`, which reordered every search.
- **`auto_routing.enabled: 0`** (or `"false"`, `"off"`) turns automatic routing off, and the next `config` command no longer writes it back as `true`.
- **Clearer failures.** A setup error no longer carries the Serper fallback attempt; a provider cut off by the deadline is listed; a missing page lists only the provider that reported it, without untried providers or a fallback that did not happen.
- **Robustness.** A config.json with a number too large for a float no longer fails every search; URLs over 8192 characters are rejected before any provider call; DonSeTch gets its configured `donsetch.timeout` (and its full time when the binary comes from config.json); a damaged search-cache file is a miss.
- **Jev status** counts only keys the runtime reads; `jev.api_key_file` in config.json is named once in the log.

## Checked before release

- Each fix has a test that fails without it; full suite green on Python 3.10, 3.12 and 3.14, also with an old web-search-plus-mcp installed in the same interpreter.
- Separate test installation with a real MCP stdio client: all scenarios pass, including the setup keys matching the error, every suggested command accepted by the CLI, DonSeTch with `timeout: 300`, and a real search, research call and 404 extract.
- The provider-try engine was compared with the previous one over 12,000 generated scenarios: no difference.
