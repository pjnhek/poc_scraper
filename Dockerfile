FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY src ./src
COPY evals ./evals
COPY configs ./configs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.11-slim
COPY --from=builder /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    MCP_DEMO_MODE=1 \
    MCP_HTTP_HOST=0.0.0.0
EXPOSE 8000
CMD ["python", "-m", "src.mcp_server", "--transport", "http"]
