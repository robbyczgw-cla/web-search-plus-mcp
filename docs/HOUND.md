# Hound local provider

`web-search-plus-mcp` 1.2 can use [Hound](https://github.com/dondai1234/master-fetch)
as an optional local provider for both source discovery and URL extraction.

Hound is an independent MIT-licensed project created and maintained by
[Bishesh Bhandari (`dondai1234`)](https://github.com/dondai1234). It is not
bundled, vendored, or forked by Web Search Plus. The MCP server connects to a
separately installed Hound sidecar through MCP Streamable HTTP.

The integration is tested with `hound-mcp 11.1.6`.

## What “keyless” means

Hound does not require a commercial search API key. It queries supported public
search engines and target sites from the machine where its sidecar runs.

Keyless does **not** mean offline, anonymous, unlimited, or free of operating
cost:

- the sidecar uses local CPU, memory, disk, and network bandwidth;
- search engines and target sites still see the machine's public IP address;
- engines may throttle, challenge, or change their public responses;
- browser-backed extraction is slower and may require Chromium;
- there is no provider SLA or guaranteed result quality.

Hound is therefore `explicit-only` by default. It is advertised in the public
provider schema, but it does not join automatic Search or Extract routing unless
an operator opts in.

## Requirements

- Python 3.11 or newer for Hound
- `hound-mcp 11.1.6` or a compatible newer 11.x release
- Hound bound to `127.0.0.1` or `::1`
- `web-search-plus-mcp 1.2.0` or newer
- Chromium only when browser-backed rendering is required

## Install Hound separately

A dedicated virtual environment keeps the optional sidecar isolated from the
MCP server:

```bash
python3.11 -m venv ~/.local/share/hound-wsp/venv
~/.local/share/hound-wsp/venv/bin/pip install "hound-mcp[all]>=11.1.6,<12"
~/.local/share/hound-wsp/venv/bin/hound --doctor
```

Optional browser runtime:

```bash
~/.local/share/hound-wsp/venv/bin/playwright install chromium
```

Start the Streamable-HTTP sidecar on loopback only:

```bash
~/.local/share/hound-wsp/venv/bin/hound \
  --http \
  --host 127.0.0.1 \
  --port 8765 \
  --cache-ttl 0
```

Do not bind the service to `0.0.0.0` or expose it through a public reverse
proxy. Hound is a retrieval worker, not a public unauthenticated API gateway.

## Configure the MCP host

Pass the endpoint to the `web-search-plus-mcp` process:

```json
{
  "mcpServers": {
    "web-search-plus": {
      "command": "uvx",
      "args": ["web-search-plus-mcp==1.2.0"],
      "env": {
        "HOUND_MCP_URL": "http://127.0.0.1:8765/mcp"
      }
    }
  }
}
```

Only uncredentialed HTTP loopback endpoints are accepted. Hostnames, public IPs,
URL user information, query strings, and fragments fail closed.

## Use Hound explicitly

Search arguments:

```json
{
  "query": "Python programming language official website",
  "provider": "hound",
  "count": 5
}
```

Extract arguments:

```json
{
  "urls": ["https://example.com"],
  "provider": "hound",
  "format": "markdown",
  "render_js": false
}
```

## Optional automatic routing

Keep the default for predictable operation. If the operator accepts Hound's
latency and public-engine variability, opt it into automatic routing:

```bash
web-search-plus-mcp config set-auto-allow hound on
```

Disable it again without removing the explicit provider:

```bash
web-search-plus-mcp config set-auto-allow hound off
```

Automatic participation still requires `HOUND_MCP_URL` and respects disabled
providers and separate Search/Extract priorities.

## Security and cache ownership

- Web Search Plus validates user-supplied extraction URLs before provider
  dispatch, including private/internal target and DNS-rebinding checks.
- The adapter accepts only literal IPv4 or IPv6 loopback MCP endpoints.
- Redirects and proxy-environment inheritance are disabled for the MCP bridge.
- The adapter asks Hound not to cache Search or Extract responses; Web Search
  Plus remains the owner of cache identity, freshness, receipts, and policy.
- Errors are projected as typed provider failures instead of leaking transport
  tracebacks through the MCP tool response.

## Attribution

Hound / Master Fetch is copyright its contributors and distributed under the
MIT License. Project and license details are available in the
[upstream repository](https://github.com/dondai1234/master-fetch).
