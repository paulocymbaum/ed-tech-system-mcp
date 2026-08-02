"""Cache-aside decorators for domain ports."""

from __future__ import annotations

import json
from typing import Literal

from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRuleSet,
    ICacheStore,
    build_cache_key,
)
from mcp_server.domain.interfaces import (
    IDataRepository,
    IEmbeddingProvider,
    ISearchClient,
    IVectorRetriever,
    IVideoSearchClient,
)
from mcp_server.domain.port_cache_trace import (
    record_embedding_cache_status,
    record_retrieval_cache_status,
)
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter, DocumentHit, VideoResult
from mcp_server.infrastructure.cache_aside import run_cache_aside
from mcp_server.infrastructure.cache_serialization import (
    deserialize_chunks,
    deserialize_documents,
    deserialize_snippets,
    deserialize_videos,
    serialize_chunks,
    serialize_documents,
    serialize_snippets,
    serialize_videos,
)
from mcp_server.infrastructure.port_observability import port_call_span


class CachedDataRepository(IDataRepository):
    """Cache-aside wrapper for document retrieval."""

    def __init__(
        self,
        inner: IDataRepository,
        cache: ICacheStore,
        rules: CacheRuleSet,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules

    async def find_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        filters: ChunkRetrievalFilter | None = None,
    ) -> list[DocumentHit]:
        operation = CacheOperationType.SUPABASE_FIND_DOCUMENTS
        filter_payload = (filters or ChunkRetrievalFilter()).model_dump(exclude_none=True)
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                return await self._inner.find_documents(query, limit=limit, filters=filters)

            key = build_cache_key(
                operation,
                {"query": query, "limit": limit, "filters": filter_payload},
                prefix=rule.key_prefix,
            )
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_documents,
                deserialize=deserialize_documents,
                loader=lambda: self._inner.find_documents(query, limit=limit, filters=filters),
            )


class CachedSearchClient(ISearchClient):
    """Cache-aside wrapper for web search."""

    def __init__(
        self,
        inner: ISearchClient,
        cache: ICacheStore,
        rules: CacheRuleSet,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        operation = CacheOperationType.WEB_SEARCH
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                return await self._inner.search(query, max_results=max_results)

            key = build_cache_key(
                operation,
                {"query": query, "max_results": max_results},
                prefix=rule.key_prefix,
            )
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_snippets,
                deserialize=deserialize_snippets,
                loader=lambda: self._inner.search(query, max_results=max_results),
            )


class CachedVideoSearchClient(IVideoSearchClient):
    """Cache-aside wrapper for video search."""

    def __init__(
        self,
        inner: IVideoSearchClient,
        cache: ICacheStore,
        rules: CacheRuleSet,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        operation = CacheOperationType.YOUTUBE_SEARCH_VIDEOS
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                return await self._inner.search_videos(
                    query,
                    max_results=max_results,
                    language=language,
                    safe_search=safe_search,
                )

            key = build_cache_key(
                operation,
                {
                    "query": query,
                    "max_results": max_results,
                    "language": language,
                    "safe_search": safe_search,
                },
                prefix=rule.key_prefix,
            )
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_videos,
                deserialize=deserialize_videos,
                loader=lambda: self._inner.search_videos(
                    query,
                    max_results=max_results,
                    language=language,
                    safe_search=safe_search,
                ),
            )


class CachedEmbeddingProvider(IEmbeddingProvider):
    """Cache-aside wrapper for query embedding vectors."""

    def __init__(
        self,
        inner: IEmbeddingProvider,
        cache: ICacheStore,
        rules: CacheRuleSet,
        *,
        model_id: str,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules
        self._model_id = model_id

    @property
    def dimensions(self) -> int:
        return self._inner.dimensions

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        operation = CacheOperationType.EMBEDDING_QUERY
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                record_embedding_cache_status("disabled")
                return await self._inner.embed_queries(texts)

            cached_vectors: list[list[float] | None] = [None] * len(texts)
            missing_indices: list[int] = []
            missing_texts: list[str] = []

            for index, text in enumerate(texts):
                key = build_cache_key(
                    operation,
                    {
                        "normalized_query": text.strip().lower(),
                        "embedding_model_id": self._model_id,
                    },
                    prefix=rule.key_prefix,
                )
                payload = await self._cache.get(key)
                if payload is None:
                    missing_indices.append(index)
                    missing_texts.append(text)
                    continue
                cached_vectors[index] = json.loads(payload.decode("utf-8"))

            if missing_texts:
                computed = await self._inner.embed_queries(missing_texts)
                for offset, index in enumerate(missing_indices):
                    vector = computed[offset]
                    cached_vectors[index] = vector
                    key = build_cache_key(
                        operation,
                        {
                            "normalized_query": texts[index].strip().lower(),
                            "embedding_model_id": self._model_id,
                        },
                        prefix=rule.key_prefix,
                    )
                    await self._cache.set(
                        key,
                        json.dumps(vector).encode("utf-8"),
                        rule.ttl_seconds,
                    )

            span.cache = "miss" if missing_texts else "hit"
            record_embedding_cache_status(span.cache)
            return [vector for vector in cached_vectors if vector is not None]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await self._inner.embed_passages(texts)


class CachedVectorRetriever(IVectorRetriever):
    """Cache-aside wrapper for vector/hybrid chunk retrieval."""

    def __init__(
        self,
        inner: IVectorRetriever,
        cache: ICacheStore,
        rules: CacheRuleSet,
        *,
        model_id: str,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules
        self._model_id = model_id

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        operation = CacheOperationType.VECTOR_RETRIEVE
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                record_retrieval_cache_status("disabled")
                return await self._inner.retrieve(
                    query_embedding,
                    limit=limit,
                    filters=filters,
                    mode=mode,
                    query_text=query_text,
                )

            key = build_cache_key(
                operation,
                {
                    "query_embedding": query_embedding,
                    "embedding_model_id": self._model_id,
                    "retrieval_mode": mode,
                    "course_id": filters.course_id,
                    "tags": filters.tags,
                    "language": filters.language,
                    "retrieve_limit": limit,
                    "query_text": query_text,
                },
                prefix=rule.key_prefix,
            )
            result = await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_chunks,
                deserialize=deserialize_chunks,
                loader=lambda: self._inner.retrieve(
                    query_embedding,
                    limit=limit,
                    filters=filters,
                    mode=mode,
                    query_text=query_text,
                ),
            )
            record_retrieval_cache_status(span.cache)
            return result
