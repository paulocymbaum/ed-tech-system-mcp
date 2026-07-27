"""Supabase pgvector RPC retriever."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

from supabase import Client, create_client

from mcp_server.domain.interfaces import IVectorRetriever
from mcp_server.domain.invariants import require_credential, require_positive_int
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter
from mcp_server.infrastructure.retrieval.chunk_hit_mapping import row_to_chunk_hit


def _filter_payload(filters: ChunkRetrievalFilter) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if filters.course_id is not None:
        payload["course_id"] = filters.course_id
    if filters.language is not None:
        payload["language"] = filters.language
    if filters.tags is not None:
        payload["tags"] = filters.tags
    return payload


def _row_to_chunk_hit(row: dict[str, Any]) -> ChunkHit:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return row_to_chunk_hit(
        chunk_id=str(row["id"]),
        document_id=str(row["document_id"]),
        content=str(row["content"]),
        score=float(row.get("score", 0.0)),
        title=row.get("title"),
        metadata=metadata,
    )


class SupabasePgvectorRetriever(IVectorRetriever):
    """Retrieve chunks via Supabase ``match_chunks`` / ``hybrid_search_chunks`` RPCs."""

    @property
    def supports_hybrid_fts(self) -> bool:
        return True

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self._supabase_url = supabase_url
        self._service_role_key = service_role_key
        self._client: Client | None = None

    def _client_or_create(self) -> Client:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        if self._client is None:
            self._client = create_client(self._supabase_url, self._service_role_key)
        return self._client

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        limit = require_positive_int(limit, field="limit")
        return await asyncio.to_thread(
            self._retrieve_sync,
            query_embedding,
            limit,
            filters,
            mode,
            query_text,
        )

    def _retrieve_sync(
        self,
        query_embedding: list[float],
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None,
    ) -> list[ChunkHit]:
        client = self._client_or_create()
        filter_payload = _filter_payload(filters)

        if mode == "hybrid":
            if query_text is None:
                msg = "query_text is required for hybrid retrieval mode"
                raise ValueError(msg)
            response = client.rpc(
                "hybrid_search_chunks",
                {
                    "query_text": query_text,
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter": filter_payload,
                },
            ).execute()
        else:
            response = client.rpc(
                "match_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter": filter_payload,
                },
            ).execute()

        rows = cast(list[dict[str, Any]], response.data or [])
        return [_row_to_chunk_hit(row) for row in rows]
