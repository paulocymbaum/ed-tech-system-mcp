"""Tests for workflow UI CORS when the SPA is hosted on a remote platform."""

from __future__ import annotations

from mcp_server.interface.local_ui.cors import resolve_workflow_ui_cors


def test_development_includes_localhost_origins() -> None:
    origins, regex = resolve_workflow_ui_cors(app_env="development")
    assert "http://127.0.0.1:4173" in origins
    assert regex is None


def test_production_allows_hosted_preview_regex() -> None:
    origins, regex = resolve_workflow_ui_cors(
        app_env="production",
        configured_origins="https://ed-tech-system-mcp.onrender.com",
        allow_preview_deployments=True,
    )
    assert "https://ed-tech-system-mcp.onrender.com" in origins
    assert regex == r"https://.*\.(onrender|vercel)\.app"


def test_production_can_disable_hosted_preview_regex() -> None:
    _origins, regex = resolve_workflow_ui_cors(
        app_env="production",
        configured_origins="https://ed-tech-system-mcp.onrender.com",
        allow_preview_deployments=False,
    )
    assert regex is None
