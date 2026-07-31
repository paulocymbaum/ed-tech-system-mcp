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
    assert 'CMD ["mcp-server"]' in content
    assert "MCP_TRANSPORT=streamable-http" in content
    assert "MCP_HOST=0.0.0.0" in content


def test_dockerfile_healthcheck_hits_health_route() -> None:
    content = _read(DOCKERFILE)
    assert "/health" in content
    assert "HEALTHCHECK" in content


def test_compose_maps_port_and_cache_volume() -> None:
    content = _read(COMPOSE_FILE)
    assert "${MCP_PORT:-8000}:8000" in content
    assert "mcp-cache:/app/.cache" in content
    assert "SUPABASE_URL" in content


def test_deploy_doc_documents_mcp_endpoint() -> None:
    content = _read(DEPLOY_DOC)
    assert "/mcp" in content
    assert "/health" in content
