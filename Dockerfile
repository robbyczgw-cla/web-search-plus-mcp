FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir web-search-plus-mcp
ENTRYPOINT ["web-search-plus-mcp"]
