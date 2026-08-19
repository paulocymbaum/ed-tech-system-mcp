"""Ports and constants for inbound MCP tools/call rate limiting."""

from __future__ import annotations

from abc import ABC, abstractmethod

INBOUND_RATE_LIMIT_MESSAGE = "Too many requests"

DEFAULT_INBOUND_LIMIT_PER_MINUTE = 60


class IInboundToolRateLimiter(ABC):
    """Cap tools/call per caller identity within a rolling minute."""

    @abstractmethod
    async def acquire(self, *, quota_key: str) -> None:
        """Reserve one call for quota_key or raise when the limit is exceeded."""
