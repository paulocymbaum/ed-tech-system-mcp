"""FastEmbed cross-encoder reranker (optional when RERANK_ENABLED=true)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp_server.domain.interfaces import IReranker
from mcp_server.domain.schemas import ChunkHit

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder


class FastEmbedRerankerAdapter(IReranker):
    """ONNX cross-encoder reranker via fastembed TextCrossEncoder."""

    def __init__(self, *, model_name: str, cache_dir: str) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model: TextCrossEncoder | None = None

    def _get_model(self) -> TextCrossEncoder:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
        return self._model

    def _rerank_sync(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        if not candidates:
            return []
        model = self._get_model()
        documents = [candidate.content for candidate in candidates]
        scores = list(model.rerank(query, documents))
        ranked = sorted(
            zip(candidates, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        results: list[ChunkHit] = []
        for candidate, score in ranked[:top_n]:
            results.append(
                candidate.model_copy(
                    update={"score": min(max(float(score), 0.0), 1.0)},
                )
            )
        return results

    async def rerank(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        return await asyncio.to_thread(
            self._rerank_sync,
            query,
            candidates,
            top_n=top_n,
        )
