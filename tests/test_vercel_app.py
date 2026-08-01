"""Tests for Vercel Python MCP entrypoint."""

from __future__ import annotations

import subprocess
import sys

from starlette.testclient import TestClient


def test_vercel_app_exports_asgi_app() -> None:
    from mcp_server.vercel_app import app

    assert app is not None
    assert hasattr(app, "routes")


def test_vercel_app_health_route() -> None:
    from mcp_server.vercel_app import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_vercel_app_import_does_not_load_langgraph() -> None:
    """Vercel cold start must not import LangGraph (workflow extra only)."""
    script = (
        "import importlib\n"
        "importlib.import_module('mcp_server.vercel_app')\n"
        "import sys\n"
        "print('langgraph' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
