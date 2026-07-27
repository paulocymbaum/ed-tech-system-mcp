"""Lazy wrapper so the cross-encoder is not loaded until the first rerank call."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_server.domain.interfaces import IReranker
from mcp_server.domain.schemas import ChunkHit

if TYPE_CHECKING:
    from mcp_server.infrastructure.rerank.fastembed_reranker import FastEmbedRerankerAdapter

logger = logging.getLogger(__name__)


class LazyFastEmbedReranker(IReranker):
    """Defer FastEmbed model load until ``rerank`` is invoked (UI opt-in path)."""

    def __init__(self, *, model_name: str, cache_dir: str) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._delegate: FastEmbedRerankerAdapter | None = None

    @property
    def is_pass_through(self) -> bool:
        return False

    def _delegate_or_create(self) -> FastEmbedRerankerAdapter:
        if self._delegate is None:
            from mcp_server.infrastructure.rerank.fastembed_reranker import (
                FastEmbedRerankerAdapter,
            )

            logger.info(
                "Loading reranker model %s (first run may download ONNX weights; can take 1–3 min)",
                self._model_name,
            )
            self._delegate = FastEmbedRerankerAdapter(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
        return self._delegate

    async def rerank(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        delegate = self._delegate_or_create()
        return await delegate.rerank(query, candidates, top_n=top_n)
