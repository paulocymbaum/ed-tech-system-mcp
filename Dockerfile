# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ARCHITECTURE.md config.json ./
COPY src ./src
COPY scripts/ci/warm_embedding_cache.py ./scripts/ci/warm_embedding_cache.py

RUN uv sync --frozen --no-dev --extra full

ENV EMBEDDING_CACHE_DIR=/app/model-cache/fastembed
ENV HF_HOME=/tmp/hf
ENV XDG_CACHE_HOME=/tmp
RUN mkdir -p /app/model-cache/fastembed && uv run python scripts/ci/warm_embedding_cache.py

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder --chown=appuser:appuser /app /app

RUN mkdir -p /tmp/hf /tmp/app-cache && chown -R appuser:appuser /tmp/hf /tmp/app-cache

ENV PATH="/app/.venv/bin:$PATH"
ENV APP_ENV=production
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV FASTMCP_MASK_ERROR_DETAILS=true
ENV PYTHONUNBUFFERED=1
ENV EMBEDDING_CACHE_DIR=/app/model-cache/fastembed
ENV EMBEDDING_WARM_ON_BOOT=false
ENV HF_HOME=/tmp/hf
ENV XDG_CACHE_HOME=/tmp
ENV GROQ_MODEL_CATALOG_CACHE_PATH=/tmp/app-cache/groq_model_catalog.json

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["mcp-server"]
