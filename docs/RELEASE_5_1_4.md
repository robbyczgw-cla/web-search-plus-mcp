# web-search-plus-mcp 5.1.4

Released 2026-10-30. Contains everything from 5.1.3, which was tagged on GitHub but not published to PyPI: compact responses by default and the Hermes Web Search Plus 5.1.6 engine fixes. See [RELEASE_5_1_3.md](RELEASE_5_1_3.md).

## Fixed

- Compact `web_search` output caps each snippet at 1,200 characters, cut at a word boundary with a `[TRUNCATED: showing first N of M characters]` marker, the same limit the Hermes plugin uses for display. Some providers return whole page sections as a snippet. In the release smoke test, Exa returned 21,830 characters for one result, and one five-result compact search came to ~32 KB. `detail: "full"` keeps the original text.

## Measured

Real Claude Code runs on 2026-10-30, eight results per search: about 800 to 1,600 tokens per compact search, against ~6,000 with 5.1.2.
