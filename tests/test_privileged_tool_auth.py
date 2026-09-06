"""Privileged MCP tool auth (caller JWT header)."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from mcp_server.application.mcp_tool_auth_runtime import (
    PRIVILEGED_TOOLS,
    McpToolAuthRuntime,
    set_mcp_tool_auth_runtime,
)
from mcp_server.domain.exceptions import DomainAuthorizationError
from mcp_server.interface import privileged_tool_auth as privileged_mod
from mcp_server.interface.privileged_tool_auth import _enforce_caller


@dataclass
class FakeIdentity:
    user_id: str = "user-1"
    members: frozenset[tuple[str, str]] = frozenset({("user-1", "tenant-1")})

    def user_id_from_jwt(self, caller_jwt: str) -> str:
        if caller_jwt != "valid-jwt":
            raise DomainAuthorizationError("Could not verify caller")
        return self.user_id

    def is_tenant_member(self, *, user_id: str, tenant_id: str) -> bool:
        return (user_id, tenant_id) in self.members


async def test_enforce_caller_rejects_missing_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.privileged_tool_auth._caller_jwt_from_headers",
        lambda: "",
    )
    runtime = McpToolAuthRuntime(require_caller_jwt=True, identity=FakeIdentity())
    with pytest.raises(DomainAuthorizationError):
        await _enforce_caller(
            runtime,
            "project_review",
            {"user_id": "user-1", "tenant_id": "tenant-1"},
        )


async def test_enforce_caller_rejects_user_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.privileged_tool_auth._caller_jwt_from_headers",
        lambda: "valid-jwt",
    )
    runtime = McpToolAuthRuntime(require_caller_jwt=True, identity=FakeIdentity())
    with pytest.raises(DomainAuthorizationError):
        await _enforce_caller(
            runtime,
            "collect_project_review_context",
            {"user_id": "other", "tenant_id": "tenant-1"},
        )


async def test_enforce_caller_accepts_matching_member(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.privileged_tool_auth._caller_jwt_from_headers",
        lambda: "valid-jwt",
    )
    runtime = McpToolAuthRuntime(require_caller_jwt=True, identity=FakeIdentity())
    await _enforce_caller(
        runtime,
        "project_review",
        {"user_id": "user-1", "tenant_id": "tenant-1"},
    )


def test_require_inbound_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("MCP_REQUIRE_INBOUND_TOKEN", "true")
    from mcp_server.settings import Settings

    settings = Settings()  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="MCP_INBOUND_TOKEN"):
        settings.assert_inbound_token_if_required()


def test_http_transport_defaults_auth_flags_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("MCP_REQUIRE_INBOUND_TOKEN", raising=False)
    monkeypatch.delenv("MCP_REQUIRE_CALLER_JWT", raising=False)
    from mcp_server.settings import Settings

    settings = Settings()  # type: ignore[call-arg]
    assert settings.mcp_require_inbound_token is True
    assert settings.mcp_require_caller_jwt is True
    with pytest.raises(RuntimeError, match="MCP_INBOUND_TOKEN"):
        settings.assert_inbound_token_if_required()


def test_stdio_transport_keeps_auth_flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("MCP_REQUIRE_INBOUND_TOKEN", raising=False)
    monkeypatch.delenv("MCP_REQUIRE_CALLER_JWT", raising=False)
    from mcp_server.settings import Settings

    settings = Settings()  # type: ignore[call-arg]
    assert settings.mcp_transport == "stdio"
    assert settings.mcp_require_inbound_token is False
    assert settings.mcp_require_caller_jwt is False


def test_http_transport_allows_explicit_auth_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_REQUIRE_INBOUND_TOKEN", "false")
    monkeypatch.setenv("MCP_REQUIRE_CALLER_JWT", "false")
    from mcp_server.settings import Settings

    settings = Settings()  # type: ignore[call-arg]
    assert settings.mcp_require_inbound_token is False
    assert settings.mcp_require_caller_jwt is False


def test_set_runtime_can_disable_gate() -> None:
    set_mcp_tool_auth_runtime(McpToolAuthRuntime(require_caller_jwt=False, identity=None))
    runtime = McpToolAuthRuntime(require_caller_jwt=False, identity=None)
    assert runtime.require_caller_jwt is False


def test_privileged_auth_offloads_sync_identity_to_thread() -> None:
    source = inspect.getsource(privileged_mod._enforce_caller)
    assert "asyncio.to_thread" in source
    assert "user_id_from_jwt" in source
    assert "is_tenant_member" in source


def test_search_web_is_privileged() -> None:
    assert "search_web" in PRIVILEGED_TOOLS
    assert "search_youtube" in PRIVILEGED_TOOLS
