# web-search-plus-mcp 4.3.3

Matches Hermes Web Search Plus 4.3.3.

## Fixed

- **Internationalized hostnames in `web_extract`.** 4.3.2 rejected URLs such as `https://müller.de`. They are now converted to punycode (IDNA 2008, as browsers do) and the converted URL is what gets validated and passed to the provider, so the check and the fetch read the same host. Labels that mix scripts, use compatibility characters such as fullwidth letters or ideographic full stops, or are not valid IDNA are still rejected. `idna` is now a declared dependency.

## Clarified

- The same-origin redirect rule from 4.3.2 applies to the HTTP client that calls provider APIs (provider API calls, not the pages you extract). Extracting `http://example.at` or a page that redirects from apex to `www` is not affected.
