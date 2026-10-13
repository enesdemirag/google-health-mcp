FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY scripts/configure.py ./scripts/configure.py
RUN uv sync --frozen --no-dev --no-editable

FROM builder AS operator-setup
ENTRYPOINT ["/app/.venv/bin/python", "/app/scripts/configure.py"]

FROM python:3.12-slim
RUN useradd --create-home --uid 10002 google-health-mcp && mkdir /data && chown google-health-mcp:google-health-mcp /data
WORKDIR /app
COPY --from=builder --chown=google-health-mcp:google-health-mcp /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENV GOOGLE_HEALTH_MCP_HOST=0.0.0.0 GOOGLE_HEALTH_MCP_PORT=8001 GOOGLE_HEALTH_MCP_DATA_DIR=/data/oauth
USER google-health-mcp
EXPOSE 8001
CMD ["google-health-mcp"]
