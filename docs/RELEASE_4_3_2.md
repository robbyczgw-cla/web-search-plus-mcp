# web-search-plus-mcp 4.3.2

A security release that matches Hermes Web Search Plus 4.3.2. Upgrading is recommended.

## Fixed

- **Extract URL validation.** URLs that parse differently across URL parsers are rejected (backslash, whitespace and control characters, userinfo, percent-escaped or non-ASCII hosts, ambiguous numeric IPv4). Literal IPs, including IPv4-mapped, IPv4-compatible, NAT64 and site-local IPv6, and all DNS answers are checked for non-global ranges.
- **Credential forwarding on redirects.** The HTTP client follows only exact same-origin redirects, and its urllib opener handles http(s) only.
- **Option injection.** `include_domains`, `exclude_domains` and `urls` values that start with `-` or are empty are refused with an `invalid_request` error before any run.
- **Response size.** Wire and decoded responses are limited to 16 MiB with bounded gzip/deflate decoding.
- **Provider error text.** Provider-supplied error text is no longer passed on; errors carry a fixed message and the status code.
- **DonSeTch environment.** The child process receives an allowlisted environment.

## Behavior changes

- Redirects that change host, port or scheme fail, including http to https and apex to www.
- Provider error messages are less detailed.
- Extract rejects non-punycode IDN hosts, userinfo and short numeric IPv4 forms.

## Residual risk

The URL check runs before dispatch and is not a network boundary. DNS rebinding and redirects followed by the final fetcher need an egress policy on that fetcher.
