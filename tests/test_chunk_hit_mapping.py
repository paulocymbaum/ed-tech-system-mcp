"""Tests for chunk hit score normalization helpers."""

from __future__ import annotations

from mcp_server.infrastructure.retrieval.chunk_hit_mapping import (
    normalize_score,
    rerank_logit_to_score,
)


def test_normalize_score_clamps_to_unit_interval() -> None:
    assert normalize_score(-1.0) == 0.0
    assert normalize_score(0.5) == 0.5
    assert normalize_score(1.5) == 1.0


def test_rerank_logit_to_score_maps_negative_logits_above_zero() -> None:
    # FastEmbed BGE reranker returns negative logits; naive clamping zeroes them out.
    for logit in (-8.6, -6.2, -4.6):
        assert rerank_logit_to_score(logit) > 0.0


def test_rerank_logit_to_score_preserves_ordering() -> None:
    low = rerank_logit_to_score(-6.0)
    high = rerank_logit_to_score(-4.0)
    assert high > low


def test_rerank_logit_to_score_midpoint_is_half() -> None:
    assert rerank_logit_to_score(0.0) == 0.5
