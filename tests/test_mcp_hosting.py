"""Tests for hosted MCP transport configuration."""

from __future__ import annotations

import pytest

from mcp_server.mcp_transport import build_mcp_run_kwargs
from mcp_server.settings import Settings


def test_build_mcp_run_kwargs_defaults_to_stdio() -> None:
    kwargs = build_mcp_run_kwargs(
        transport="stdio",
        host="127.0.0.1",
        port=8000,
    )
    assert kwargs == {"transport": "stdio"}


def test_build_mcp_run_kwargs_streamable_http() -> None:
    kwargs = build_mcp_run_kwargs(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
    )
    assert kwargs == {
        "transport": "streamable-http",
        "host": "0.0.0.0",
        "port": 8000,
    }


def test_build_mcp_run_kwargs_passes_stateless_and_host_protection() -> None:
    kwargs = build_mcp_run_kwargs(
        transport="streamable-http",
        host="0.0.0.0",
        port=9000,
        stateless_http=True,
        host_origin_protection="auto",
        allowed_hosts="api.example.com",
    )
    assert kwargs["stateless_http"] is True
    assert kwargs["host_origin_protection"] == "auto"
    assert kwargs["allowed_hosts"] == ["api.example.com"]


def test_settings_parse_mcp_allowed_hosts_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "api.example.com, mcp.example.com")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.mcp_allowed_hosts == "api.example.com, mcp.example.com"
    kwargs = build_mcp_run_kwargs(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        allowed_hosts=settings.mcp_allowed_hosts,
    )
    assert kwargs["allowed_hosts"] == ["api.example.com", "mcp.example.com"]
