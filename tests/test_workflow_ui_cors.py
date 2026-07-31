"""Tests for workflow UI CORS when the SPA is hosted on Vercel."""

from __future__ import annotations

from mcp_server.interface.local_ui.cors import resolve_workflow_ui_cors


def test_development_includes_localhost_origins() -> None:
    origins, regex = resolve_workflow_ui_cors(app_env="development")
    assert "http://127.0.0.1:4173" in origins
    assert regex is None


def test_production_allows_vercel_preview_regex() -> None:
    origins, regex = resolve_workflow_ui_cors(
        app_env="production",
        configured_origins="https://ed-tech-system-mcp.vercel.app",
        allow_vercel_previews=True,
    )
    assert "https://ed-tech-system-mcp.vercel.app" in origins
    assert regex == r"https://.*\.vercel\.app"


def test_production_can_disable_vercel_preview_regex() -> None:
    _origins, regex = resolve_workflow_ui_cors(
        app_env="production",
        configured_origins="https://ed-tech-system-mcp.vercel.app",
        allow_vercel_previews=False,
    )
    assert regex is None
