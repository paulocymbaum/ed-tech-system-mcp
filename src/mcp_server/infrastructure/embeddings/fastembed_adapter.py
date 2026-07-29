"""FastEmbed ONNX embedding provider with E5 query/passage prefixes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp_server.domain.interfaces import IEmbeddingProvider
from mcp_server.infrastructure.embeddings.fastembed_model_catalog import resolve_embedding_model

if TYPE_CHECKING:
    from fastembed import TextEmbedding

E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "


class FastEmbedAdapter(IEmbeddingProvider):
    """Local ONNX embeddings via fastembed (multilingual E5 default)."""

    def __init__(
        self,
        *,
        model_name: str,
        dimensions: int,
        cache_dir: str,
    ) -> None:
        resolved = resolve_embedding_model(model_name, dimensions)
        self._requested_model = resolved.requested_model
        self._model_name = resolved.model_name
        self._dimensions = resolved.dimensions
        self._use_e5_prefixes = resolved.use_e5_prefixes
        self._cache_dir = cache_dir
        self._model: TextEmbedding | None = None

    @property
    def requested_model(self) -> str:
        return self._requested_model

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self._model_name,
                cache_dir=self._cache_dir,
            )
        return self._model

    def _embed_sync(self, prefixed_texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        vectors: list[list[float]] = []
        for vector in model.embed(prefixed_texts):
            if hasattr(vector, "tolist"):
                vectors.append(vector.tolist())
            else:
                vectors.append([float(value) for value in vector])
        return vectors

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._use_e5_prefixes:
            prefixed = [f"{E5_QUERY_PREFIX}{text}" for text in texts]
        else:
            prefixed = list(texts)
        return await asyncio.to_thread(self._embed_sync, prefixed)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._use_e5_prefixes:
            prefixed = [f"{E5_PASSAGE_PREFIX}{text}" for text in texts]
        else:
            prefixed = list(texts)
        return await asyncio.to_thread(self._embed_sync, prefixed)
