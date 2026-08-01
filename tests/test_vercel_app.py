"""Tests for Vercel Python MCP entrypoint."""

from __future__ import annotations

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
