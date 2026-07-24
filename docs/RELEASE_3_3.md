# web-search-plus-mcp 3.3 release notes

`web-search-plus-mcp 3.3.0` packages the portable Web Search Plus 3.3.0 engine
for MCP clients. This release intentionally realigns the standalone package
version from 1.2.0 to 3.3.0 so the package and engine generation are obvious at
a glance. It is not a breaking change to the MCP tool surface.

## Highlights

- bounded heading-aware semantic sections for `web_extract` spans;
- provenance-safe cross-provider `snippet_aggregate` projection;
- additive `source_type` and explainable `fetch_priority` result hints;
- completion-order Research with configurable quality quorum;
- explicit `preempted_after_quorum` and cooldown diagnostics;
- repaired `quality_report=true` projection on the canonical v3 path.

## Stable MCP surface

The server still exposes exactly two tools:

- `web_search`
- `web_extract`

Their names, arguments, and legacy result fields remain compatible. New evidence
and diagnostics are additive. The stdio/subprocess boundary remains unchanged.

## Research behavior

Research providers are harvested as they complete, but public result order stays
deterministic. Once enough unique results, contributing providers, and domains
satisfy the configured quorum, unfinished providers can be cancelled and are
reported as `preempted_after_quorum` rather than silently disappearing.

Explicit Research-provider lists no longer inherit the automatic-routing
allowlist. Disabled, unconfigured, and cooldown providers are still excluded and
remain visible in diagnostics.

## MCP diagnostics

When `quality_report=true` is requested, the MCP projection now derives its
report from validated canonical results, routing receipts, provider attempts,
source diversity, and cache status. It does not issue a second provider request.

## Hound / Master-Fetch attribution

The heading-aware interaction and completion-order Research ideas are inspired
by [Hound/Master-Fetch v11.2.0](https://github.com/dondai1234/master-fetch/releases/tag/v11.2.0),
an independent MIT-licensed project created and maintained by
[Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234).

The implementation is independently reworked for Web Search Plus MCP's own
provider, provenance, budget, cache, and receipt contracts. Hound is neither
bundled nor claimed as Robby's code. The optional Hound provider connects to a
separately installed loopback sidecar.

## Upgrade

```bash
pip install --upgrade "web-search-plus-mcp==3.3.0"
```

Or pin the version in an MCP host configuration:

```json
{
  "command": "uvx",
  "args": ["web-search-plus-mcp==3.3.0"]
}
```

No configuration migration is required from 1.2.0. Hosts that pin the package
must update the pin because of the intentional version-line realignment.
