"""Cache hit/miss logging and lightweight counters."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_INFO_LOG_INTERVAL = 10


@dataclass
class OperationMetrics:
    """Per-operation cache counters."""

    hits: int = 0
    misses: int = 0


@dataclass
class CacheMetrics:
    """In-process cache counters for future metrics backends."""

    hits: int = 0
    misses: int = 0
    by_operation: dict[str, OperationMetrics] = field(default_factory=dict)


_metrics = CacheMetrics()


def get_cache_metrics() -> CacheMetrics:
    """Return the process-wide cache metrics snapshot."""
    by_operation = {
        operation: OperationMetrics(hits=op.hits, misses=op.misses)
        for operation, op in _metrics.by_operation.items()
    }
    return CacheMetrics(
        hits=_metrics.hits,
        misses=_metrics.misses,
        by_operation=by_operation,
    )


def reset_cache_metrics() -> None:
    """Reset cache counters (for tests)."""
    global _metrics
    _metrics = CacheMetrics()


def _operation_metrics(operation: str) -> OperationMetrics:
    op_metrics = _metrics.by_operation.get(operation)
    if op_metrics is None:
        op_metrics = OperationMetrics()
        _metrics.by_operation[operation] = op_metrics
    return op_metrics


def _maybe_log_hit_rate(operation: str, op_metrics: OperationMetrics) -> None:
    total = op_metrics.hits + op_metrics.misses
    if total == 0 or total % _INFO_LOG_INTERVAL != 0:
        return
    hit_rate = op_metrics.hits / total
    logger.info(
        "cache hit-rate operation=%s hits=%d misses=%d hit_rate=%.2f",
        operation,
        op_metrics.hits,
        op_metrics.misses,
        hit_rate,
    )


def record_cache_hit(operation: str, key: str) -> None:
    """Log and count a cache hit."""
    _metrics.hits += 1
    op_metrics = _operation_metrics(operation)
    op_metrics.hits += 1
    logger.debug("cache hit operation=%s key=%s", operation, key)
    _maybe_log_hit_rate(operation, op_metrics)


def record_cache_miss(operation: str, key: str) -> None:
    """Log and count a cache miss."""
    _metrics.misses += 1
    op_metrics = _operation_metrics(operation)
    op_metrics.misses += 1
    logger.debug("cache miss operation=%s key=%s", operation, key)
    _maybe_log_hit_rate(operation, op_metrics)
