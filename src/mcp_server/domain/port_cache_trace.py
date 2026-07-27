"""Per-request cache status bridge from infrastructure port spans to application nodes."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Literal

CacheSpanStatus = Literal["hit", "miss", "disabled"]

_embedding_cache_status: ContextVar[CacheSpanStatus | None] = ContextVar(
    "embedding_cache_status",
    default=None,
)
_retrieval_cache_status: ContextVar[CacheSpanStatus | None] = ContextVar(
    "retrieval_cache_status",
    default=None,
)


def record_embedding_cache_status(status: CacheSpanStatus) -> None:
    """Record embedding port cache outcome for the current async context."""
    _embedding_cache_status.set(status)


def record_retrieval_cache_status(status: CacheSpanStatus) -> None:
    """Record vector retrieval port cache outcome for the current async context."""
    _retrieval_cache_status.set(status)


def consume_embedding_cache_hit() -> bool | None:
    """Return cache hit/miss when caching was active; ``None`` when disabled or unset."""
    status = _embedding_cache_status.get()
    _embedding_cache_status.set(None)
    if status == "hit":
        return True
    if status == "miss":
        return False
    return None


def consume_retrieval_cache_hit() -> bool | None:
    """Return cache hit/miss when caching was active; ``None`` when disabled or unset."""
    status = _retrieval_cache_status.get()
    _retrieval_cache_status.set(None)
    if status == "hit":
        return True
    if status == "miss":
        return False
    return None
