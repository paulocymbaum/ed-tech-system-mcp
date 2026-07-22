"""Shared helpers for mapping store rows to domain ChunkHit entities."""

from __future__ import annotations

import math
from typing import Any

from mcp_server.domain.schemas import ChunkHit


def normalize_score(raw: float) -> float:
    """Clamp retrieval scores to the domain ``ChunkHit`` range [0, 1]."""
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def rerank_logit_to_score(raw: float) -> float:
    """Map cross-encoder logits to a bounded similarity score for metrics/UI."""
    if raw >= 0.0:
        return normalize_score(1.0 / (1.0 + math.exp(-raw)))
    exp_raw = math.exp(raw)
    return normalize_score(exp_raw / (1.0 + exp_raw))


def row_to_chunk_hit(
    *,
    chunk_id: str,
    document_id: str,
    content: str,
    score: float,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChunkHit:
    """Build a ``ChunkHit`` from normalized store fields."""
    meta = metadata or {}
    if not isinstance(meta, dict):
        meta = {}
    return ChunkHit(
        id=chunk_id,
        document_id=document_id,
        title=title,
        content=content,
        score=normalize_score(score),
        metadata={str(k): str(v) for k, v in meta.items()},
    )
