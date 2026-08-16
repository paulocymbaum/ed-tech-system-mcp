"""Refuse privileged MCP tools without a verified caller JWT (header, not tool args)."""

from __future__ import annotations

import hmac
from typing import Any

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import CallToolRequestParams

from mcp_server.application.mcp_tool_auth_runtime import (
    CALLER_JWT_HEADER,
    PRIVILEGED_TOOLS,
    get_mcp_tool_auth_runtime,
)
from mcp_server.domain.exceptions import DomainAuthorizationError
from mcp_server.interface.error_mapping import raise_as_mcp_error


def _tool_arguments(message: CallToolRequestParams) -> dict[str, Any]:
    raw = getattr(message, "arguments", None)
    if isinstance(raw, dict):
        return raw
    return {}


def _caller_jwt_from_headers() -> str:
    headers = get_http_headers()
    value = headers.get(CALLER_JWT_HEADER, "")
    return value.removeprefix("Bearer ").strip()


class PrivilegedToolAuthMiddleware(Middleware):
    """Gate privileged tools when ``MCP_REQUIRE_CALLER_JWT`` is enabled."""

    async def on_call_tool(self, context: MiddlewareContext[CallToolRequestParams], call_next):
        runtime = get_mcp_tool_auth_runtime()
        if runtime is None or not runtime.require_caller_jwt or runtime.identity is None:
            return await call_next(context)

        name = getattr(context.message, "name", "")
        if name not in PRIVILEGED_TOOLS:
            return await call_next(context)

        try:
            _enforce_caller(runtime, name, _tool_arguments(context.message))
        except DomainAuthorizationError as exc:
            raise_as_mcp_error(exc)
        return await call_next(context)


def _enforce_caller(runtime: Any, tool_name: str, arguments: dict[str, Any]) -> None:
    _ = tool_name
    identity = runtime.identity
    caller_jwt = _caller_jwt_from_headers()
    if not caller_jwt:
        raise DomainAuthorizationError("Caller JWT is required")
    user_id = identity.user_id_from_jwt(caller_jwt)

    requested_user = arguments.get("user_id")
    if isinstance(requested_user, str) and requested_user.strip() and requested_user != user_id:
        raise DomainAuthorizationError("Caller does not match user_id")

    manager_jwt = arguments.get("manager_jwt")
    if isinstance(manager_jwt, str) and manager_jwt.strip():
        provided = manager_jwt.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(provided, caller_jwt):
            raise DomainAuthorizationError("Caller does not match manager_jwt")

    tenant_id = arguments.get("tenant_id")
    if isinstance(tenant_id, str) and tenant_id.strip():
        if not identity.is_tenant_member(user_id=user_id, tenant_id=tenant_id.strip()):
            raise DomainAuthorizationError("Caller is not a member of this tenant")
