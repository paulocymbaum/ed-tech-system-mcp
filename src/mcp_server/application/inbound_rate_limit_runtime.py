"""Runtime for inbound MCP tools/call quotas (HTTP only)."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_server.domain.inbound_rate_limit import IInboundToolRateLimiter


@dataclass(frozen=True)
class InboundRateLimitRuntime:
    enabled: bool
    limiter: IInboundToolRateLimiter | None


_runtime: InboundRateLimitRuntime | None = None


def set_inbound_rate_limit_runtime(runtime: InboundRateLimitRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def get_inbound_rate_limit_runtime() -> InboundRateLimitRuntime | None:
    return _runtime
