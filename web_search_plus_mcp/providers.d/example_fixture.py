"""Non-production SDK fixture; it never performs a network request."""

from wsp_sdk import ProviderSpec, search_result, source_result


def execute_search(search_module, prov, args, key, config, routing_info):
    """Return deterministic source evidence for discovery and SDK tests only."""
    query = getattr(args, "query", "")
    return search_result(
        prov,
        query,
        [
            source_result(
                "https://example.invalid/wsp-sdk-fixture",
                title="WSP Provider SDK fixture",
                snippet="Non-production fixture result; no network request was made.",
            )
        ],
        metadata={"fixture": True, "network": False},
    )


# This module proves the zero-core-edit path.  It remains explicit-only even
# when keyless public access is enabled, so it is never auto-routed by default.
PROVIDER = ProviderSpec(
    id="example-fixture",
    kind="search",
    env_var="EXAMPLE_FIXTURE_API_KEY",
    display_name="Example fixture (non-production)",
    description="Non-production, no-network Provider SDK fixture used to verify automatic discovery.",
    config_section="example_fixture",
    capability_labels=("search", "fixture", "non-production"),
    keyless=True,
    auto_allowed_by_default=False,
    free_tier="Fixture only (no network)",
    signup_url="https://example.invalid/wsp-provider-sdk",
    execute_search=execute_search,
    production=False,
)
