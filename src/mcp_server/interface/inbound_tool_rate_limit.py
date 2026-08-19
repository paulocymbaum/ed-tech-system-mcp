"""Refuse tools/call bursts per inbound token or caller JWT (hashed)."""

from __future__ import annotations

import hashlib

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import CallToolRequestParams

from mcp_server.application.inbound_rate_limit_runtime import get_inbound_rate_limit_runtime
from mcp_server.application.mcp_tool_auth_runtime import CALLER_JWT_HEADER
from mcp_server.domain.exceptions import ExternalRateLimitError
from mcp_server.interface.error_mapping import raise_as_mcp_error


def _quota_key_from_headers() -> str:
    try:
        headers = get_http_headers()
    except Exception:
        return "anonymous"
    auth = headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        token = headers.get(CALLER_JWT_HEADER, "").removeprefix("Bearer ").strip()
    if not token:
        return "anonymous"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InboundToolRateLimitMiddleware(Middleware):
    """Bound tools/call when inbound rate limiting is enabled (HTTP transports)."""

    async def on_call_tool(self, context: MiddlewareContext[CallToolRequestParams], call_next):
        runtime = get_inbound_rate_limit_runtime()
        if runtime is None or not runtime.enabled or runtime.limiter is None:
            return await call_next(context)
        try:
            await runtime.limiter.acquire(quota_key=_quota_key_from_headers())
        except ExternalRateLimitError as exc:
            raise_as_mcp_error(exc)
        return await call_next(context)
