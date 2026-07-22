"""Structured timing spans for domain port calls."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

CacheSpanStatus = Literal["hit", "miss", "disabled"]


@dataclass
class PortCallSpan:
    """Mutable span state collected during a port call."""

    operation: str
    cache: CacheSpanStatus = "disabled"


def log_port_call(operation: str, duration_ms: float, cache: CacheSpanStatus) -> None:
    """Log a high-signal port-call timing span at INFO."""
    logger.info(
        "port call operation=%s duration_ms=%.2f cache=%s",
        operation,
        duration_ms,
        cache,
    )


@asynccontextmanager
async def port_call_span(operation: str) -> AsyncIterator[PortCallSpan]:
    """Measure and log duration for a single port call."""
    span = PortCallSpan(operation=operation)
    start = time.perf_counter()
    try:
        yield span
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_port_call(span.operation, duration_ms, span.cache)
