"""Supabase repository implementation."""

from __future__ import annotations

import asyncio
from typing import Literal, cast

from supabase import Client, create_client

from mcp_server.domain.interfaces import IEmbeddingProvider, IDataRepository, IVectorRetriever
from mcp_server.domain.invariants import (
    require_credential,
    require_non_empty_text,
    require_positive_int,
)
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter, DocumentHit


def _chunks_to_document_hits(chunks: list[ChunkHit], *, limit: int) -> list[DocumentHit]:
    """Merge chunk hits into one DocumentHit per document (best-scoring chunk wins)."""
    by_document: dict[str, ChunkHit] = {}
    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        if chunk.document_id not in by_document:
            by_document[chunk.document_id] = chunk
        if len(by_document) >= limit:
            break

    hits: list[DocumentHit] = []
    for document_id, chunk in by_document.items():
        hits.append(
            DocumentHit(
                id=document_id,
                title=chunk.title or document_id,
                content=chunk.content,
                metadata=chunk.metadata,
            )
        )
    return hits[:limit]


class SupabaseRepository(IDataRepository):
    """Adapter for Supabase-backed document storage."""

    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        *,
        embedding_provider: IEmbeddingProvider | None = None,
        vector_retriever: IVectorRetriever | None = None,
        retrieval_mode: Literal["vector", "hybrid"] = "hybrid",
    ) -> None:
        self._supabase_url = supabase_url
        self._service_role_key = service_role_key
        self._embedding_provider = embedding_provider
        self._vector_retriever = vector_retriever
        self._retrieval_mode = retrieval_mode
        self._client: Client | None = None

    def _client_or_create(self) -> Client:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        if self._client is None:
            self._client = create_client(self._supabase_url, self._service_role_key)
        return self._client

    async def has_documents(
        self,
        *,
        filters: ChunkRetrievalFilter | None = None,
    ) -> bool:
        """Cheap existence check against the documents table; no embedding model loaded."""
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")

        query = self._client_or_create().table("documents").select("id")
        if filters is not None and filters.course_id:
            query = query.eq("course_id", filters.course_id)

        response = await asyncio.to_thread(query.limit(1).execute)
        return bool(response.data)

    async def find_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        filters: ChunkRetrievalFilter | None = None,
    ) -> list[DocumentHit]:
        query = require_non_empty_text(query, field="query")
        limit = require_positive_int(limit, field="limit")
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")

        if self._embedding_provider is None or self._vector_retriever is None:
            raise NotImplementedError("SupabaseRepository.find_documents is not yet implemented")

        embeddings = await self._embedding_provider.embed_queries([query])
        embedding = embeddings[0]
        mode = self._retrieval_mode
        if mode == "hybrid" and not self._vector_retriever.supports_hybrid_fts:
            mode = "vector"

        chunks = await self._vector_retriever.retrieve(
            embedding,
            limit=max(limit * 3, limit),
            filters=filters or ChunkRetrievalFilter(),
            mode=cast(Literal["vector", "hybrid"], mode),
            query_text=query if mode == "hybrid" else None,
        )
        return _chunks_to_document_hits(chunks, limit=limit)
