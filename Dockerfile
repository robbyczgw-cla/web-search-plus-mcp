FROM python:3.12-slim

LABEL org.opencontainers.image.title="web-search-plus-mcp"
LABEL org.opencontainers.image.description="Multi-provider web search MCP server"
LABEL org.opencontainers.image.source="https://github.com/robbyczgw-cla/web-search-plus-mcp"

WORKDIR /app
RUN pip install --no-cache-dir web-search-plus-mcp

# Environment variables (optional, for tool inspection)
ENV SERPER_API_KEY=""
ENV TAVILY_API_KEY=""
ENV EXA_API_KEY=""
ENV QUERIT_API_KEY=""
ENV PERPLEXITY_API_KEY=""
ENV YOU_API_KEY=""
ENV SEARXNG_BASE_URL=""

ENTRYPOINT ["web-search-plus-mcp"]
