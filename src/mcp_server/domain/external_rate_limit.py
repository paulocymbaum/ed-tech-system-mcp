"""Ports and constants for outbound external API rate limiting."""

from __future__ import annotations

from abc import ABC, abstractmethod

EXTERNAL_RATE_LIMIT_MESSAGE = (
    "Too many external API requests in the last minute. "
    "Please wait a few minutes and try again."
)

DEFAULT_EXTERNAL_REQUEST_LIMIT_PER_MINUTE = 60


class IExternalRequestRateLimiter(ABC):
    """Port that caps outbound calls to third-party APIs within a rolling minute."""

    @abstractmethod
    def acquire_sync(self, *, provider: str) -> None:
        """Reserve quota for a sync outbound call or raise when the limit is exceeded."""

    @abstractmethod
    async def acquire(self, *, provider: str) -> None:
        """Reserve quota for an async outbound call or raise when the limit is exceeded."""
