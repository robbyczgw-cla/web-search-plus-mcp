# Contributing to web-search-plus-mcp

Thanks for helping improve the standalone MCP distribution of Web Search Plus. This repository values small, reviewable changes, source-backed behavior, stable public contracts, and tests that do not require paid provider credentials.

## Project boundaries

This repository owns the standalone Python package, MCP stdio server, CLI, packaging, generated contract schemas, and compatibility projection for the stable `web_search` and `web_extract` tools.

The portable search engine is shared conceptually with [Hermes Web Search Plus](https://github.com/robbyczgw-cla/hermes-web-search-plus), but the MCP surface is intentionally different. Do not rename the stable MCP tools to match another host, leak host-specific hooks into this package, or blindly copy runtime code across repositories.

The public contract is mechanically source-only: provider adapters return source results and extracted page content, not synthesized answers. Changes that reintroduce answer-style providers or project unsupported vendor behavior as evidence will not be accepted.

## Before opening an issue

- Search existing issues and pull requests.
- For usage questions, include the package version, Python version, MCP client, and a minimal redacted configuration shape.
- For provider failures, include the provider name, stable error code, and whether the request was explicit or auto-routed.
- Never paste API keys, tokens, full query logs, private URLs, `.env` files, or raw provider payloads.
- Report exploitable vulnerabilities privately to the maintainers instead of opening a public issue.

## Local setup

Python 3.10, 3.11, and 3.12 are exercised in GitHub Actions. Create an isolated environment and install the package with the test and build dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip build
python -m pip install -e ".[test]"
```

Do not refresh `uv.lock` or dependency constraints for an unrelated change.

## Required checks

Run the same core commands as [GitHub Actions](.github/workflows/ci.yml):

```bash
python -m pytest tests/ -q -p no:cacheprovider
ruff check --config pyproject.toml .
python -m compileall -q web_search_plus_mcp tests
python -m build
```

Changes to the portable v3 contract must also prove that committed schemas are current:

```bash
python scripts/gen_contract_v3_schemas.py --check
```

Packaging or release-facing changes must inspect both the wheel and source distribution produced under `dist/`.

Tests should be deterministic and network-free by default. Mock provider HTTP and subprocess boundaries; never make CI depend on a live credential, quota, mutable search result, or local Hound process.

## Portable engine changes

Behavior shared with Hermes Web Search Plus should normally be designed and tested upstream first, then deliberately ported here. A port must preserve this repository's MCP-specific boundaries:

- stable `web_search` and `web_extract` names and legacy-compatible projections;
- stdio lifecycle and subprocess deadlines;
- typed, secret-free errors;
- source-only provider envelopes;
- committed schemas under [`schemas/v3`](schemas/v3);
- standalone configuration, PyPI, wheel, sdist, and Docker behavior.

In the pull request, identify the upstream version or commit used as design input and list deliberate no-port decisions. “Copied from upstream” is not a verification plan.

When changing v3 request or response structures, update the contract code, regenerate schemas without `--check`, inspect the diff, and then run the check form above:

```bash
python scripts/gen_contract_v3_schemas.py
python scripts/gen_contract_v3_schemas.py --check
```

## Provider changes

Read the registry, adapter protocol, and SDK examples before adding a provider. New providers must have:

- a source-result or extraction endpoint with documented semantics;
- a registry entry and explicit Search/Extract capabilities;
- normalized, validated source-only envelopes;
- strict explicit-provider behavior and deliberate auto-routing policy;
- finite timeouts, bounded responses, sanitized failures, and no secret-bearing cache identity;
- network-free adapter, dispatch, failure, and conformance tests;
- documentation and an entry under `[Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).

External SDK providers belong under `web_search_plus_mcp/providers.d` and must satisfy the fail-closed discovery and conformance gates. Start with the shipped example fixture and its tests rather than bypassing the registry.

A separately installed provider remains a separate upstream project. Preserve license, authorship, security boundaries, and visible attribution. DonSeTch-specific constraints are documented in [`docs/DONSETCH.md`](docs/DONSETCH.md).

## MCP and compatibility changes

Treat tool names, input schemas, output projections, error codes, and default fallback behavior as public API. Add focused tests in `tests/test_server_schema.py`, `tests/test_mcp_v1_contract.py`, or the closest existing compatibility file.

Additive fields still need schema and projection tests. Breaking changes require explicit maintainer agreement, migration notes, a major version decision, and corresponding README/changelog updates.

## Security and privacy

- Credentials come from documented configuration or environment variables; never commit them or print them in diagnostics.
- Do not include query text, private URLs, provider payload fragments, headers, or credentials in stable errors.
- Preserve SSRF defenses, loopback-only sidecar validation, redirect policy, response limits, and cache ownership.
- Keep CI and unit tests network-free unless a maintainer explicitly approves a bounded opt-in integration test.
- Use clearly fake values such as `test-key`; do not use realistic token shapes in fixtures.
- Never weaken a safety gate merely to make an adapter pass.

## Documentation and changelog

User-visible behavior belongs in the [README](README.md). Provider setup and security constraints must be documented alongside the code. Keep examples executable and redact secrets.

Every user-visible, packaging, compatibility, security, or contributor-workflow change needs a concise entry under `[Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md). Do not hard-code volatile test counts or future release dates in contributor documentation.

## Pull requests

Keep each pull request focused. The description should include:

- the problem and chosen boundary;
- user-visible and compatibility impact;
- tests added or changed;
- exact commands run and their results;
- upstream provenance and no-port decisions, when relevant;
- security/privacy implications;
- release-note or changelog impact.

Before requesting review, rebase on the current default branch, run the required checks, inspect the package contents when packaging changed, and review your own diff for generated files, credentials, debug output, internal paths, and accidental unrelated lockfile churn.

Maintainers decide routing defaults, provider admission, public contract changes, compatibility breaks, releases, and whether a behavior belongs upstream before it belongs here.
