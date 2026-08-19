"""Inbound MCP tools/call rate limiter."""

from __future__ import annotations

import pytest

from mcp_server.application.inbound_rate_limit_runtime import (
    InboundRateLimitRuntime,
    set_inbound_rate_limit_runtime,
)
from mcp_server.domain.exceptions import ExternalRateLimitError
from mcp_server.domain.inbound_rate_limit import INBOUND_RATE_LIMIT_MESSAGE
from mcp_server.infrastructure.inbound_rate_limiter import (
    KeyedSlidingWindowInboundRateLimiter,
)
from mcp_server.interface.inbound_tool_rate_limit import (
    InboundToolRateLimitMiddleware,
    _quota_key_from_headers,
)


@pytest.mark.asyncio
async def test_keyed_limiter_allows_under_cap() -> None:
    limiter = KeyedSlidingWindowInboundRateLimiter(2, window_seconds=60.0)
    await limiter.acquire(quota_key="a")
    await limiter.acquire(quota_key="a")
    await limiter.acquire(quota_key="b")


@pytest.mark.asyncio
async def test_keyed_limiter_rejects_over_cap() -> None:
    limiter = KeyedSlidingWindowInboundRateLimiter(1, window_seconds=60.0)
    await limiter.acquire(quota_key="a")
    with pytest.raises(ExternalRateLimitError, match=INBOUND_RATE_LIMIT_MESSAGE):
        await limiter.acquire(quota_key="a")


@pytest.mark.asyncio
async def test_middleware_skips_when_disabled() -> None:
    set_inbound_rate_limit_runtime(InboundRateLimitRuntime(enabled=False, limiter=None))
    middleware = InboundToolRateLimitMiddleware()
    called = {"next": False}

    async def call_next(_context: object) -> str:
        called["next"] = True
        return "ok"

    result = await middleware.on_call_tool(None, call_next)  # type: ignore[arg-type]
    assert result == "ok"
    assert called["next"] is True


def test_quota_key_hashes_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.inbound_tool_rate_limit.get_http_headers",
        lambda: {"authorization": "Bearer secret-token"},
    )
    first = _quota_key_from_headers()
    second = _quota_key_from_headers()
    assert first == second
    assert "secret-token" not in first
    assert len(first) == 64
