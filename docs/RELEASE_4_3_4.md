# web-search-plus-mcp 4.3.4

Matches Hermes Web Search Plus 4.3.4.

## Fixed

- **Missing-key hints.** When a provider key is missing, the error now suggests `web-search-plus-mcp setup --preset starter`, the `.env` file or the `env` block of your MCP client config. It no longer suggests putting the key inline in `config.json`.
- **DonSeTch stderr on close.** Closing a session now lets the stderr reader finish before the pipe is closed. Previously the sanitized stderr excerpt could be lost and the reader thread could raise `ValueError` under load.

The first-run status changes in Hermes Web Search Plus 4.3.4 (`ready`, `provider_setup_required`) apply to the Hermes plugin's `setup.py`; this package's `status` and error payloads are otherwise unchanged.
