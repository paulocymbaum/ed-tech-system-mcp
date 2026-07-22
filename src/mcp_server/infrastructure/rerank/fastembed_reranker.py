"""FastEmbed cross-encoder reranker (loaded on first rerank call)."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from mcp_server.domain.interfaces import IReranker
from mcp_server.domain.schemas import ChunkHit

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

logger = logging.getLogger(__name__)

_DEFAULT_RERANK_TIMEOUT_SECONDS = 180.0
_MODEL_LOAD_LOCK = threading.Lock()


class FastEmbedRerankerAdapter(IReranker):
    """ONNX cross-encoder reranker via fastembed TextCrossEncoder."""

    def __init__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        rerank_timeout_seconds: float = _DEFAULT_RERANK_TIMEOUT_SECONDS,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._rerank_timeout_seconds = rerank_timeout_seconds
        self._model: TextCrossEncoder | None = None

    def _get_model(self) -> TextCrossEncoder:
        if self._model is not None:
            return self._model
        with _MODEL_LOAD_LOCK:
            if self._model is not None:
                return self._model
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            logger.info("Initializing reranker ONNX session for %s", self._model_name)
            self._model = TextCrossEncoder(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
            logger.info("Reranker model %s ready", self._model_name)
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
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._rerank_sync,
                    query,
                    candidates,
                    top_n=top_n,
                ),
                timeout=self._rerank_timeout_seconds,
            )
        except TimeoutError as exc:
            msg = (
                f"Reranker timed out after {self._rerank_timeout_seconds:.0f}s "
                f"(model={self._model_name}). First run may download ONNX weights; "
                "retry after the model is cached or disable rerank in the UI."
            )
            raise TimeoutError(msg) from exc
