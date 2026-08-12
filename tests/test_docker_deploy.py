"""Contract tests for MCP Docker hosting artifacts."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
DEPLOY_DOC = REPO_ROOT / "DEPLOY.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dockerfile_uses_python312_and_mcp_server_cmd() -> None:
    content = _read(DOCKERFILE)
    assert "python3.12" in content
    assert "ARCHITECTURE.md" in content
    assert "config.json" in content
    assert 'CMD ["mcp-server"]' in content
    assert "MCP_TRANSPORT=streamable-http" in content
    assert "MCP_HOST=0.0.0.0" in content


def test_dockerfile_sets_writable_cache_paths() -> None:
    content = _read(DOCKERFILE)
    assert "ENV EMBEDDING_CACHE_DIR=/app/model-cache/fastembed" in content
    assert "ENV EMBEDDING_WARM_ON_BOOT=true" in content
    assert "ENV HF_HOME=/tmp/hf" in content
    assert "ENV XDG_CACHE_HOME=/tmp" in content
    assert "ENV GROQ_MODEL_CATALOG_CACHE_PATH=/tmp/app-cache/groq_model_catalog.json" in content
    assert "warm_embedding_cache.py" in content
    assert "mkdir -p /tmp/hf /tmp/app-cache" in content
    assert "chown -R appuser:appuser /tmp/hf /tmp/app-cache" in content
    user_line = content.index("USER appuser")
    mkdir_line = content.index("mkdir -p /tmp/hf")
    assert mkdir_line < user_line


def test_dockerfile_healthcheck_hits_health_route() -> None:
    content = _read(DOCKERFILE)
    assert "/health" in content
    assert "HEALTHCHECK" in content


def test_compose_maps_port_and_cache_volume() -> None:
    content = _read(COMPOSE_FILE)
    assert "${MCP_PORT:-8000}:8000" in content
    assert "${WORKFLOW_API_PORT:-8877}:8877" in content
    assert "workflow-api" in content
    assert "mcp-cache:/app/.cache" in content
    assert "SUPABASE_URL" in content


def test_deploy_doc_documents_mcp_endpoint() -> None:
    content = _read(DEPLOY_DOC)
    assert "/mcp" in content
    assert "/health" in content
