"""ChromaDB persistent vector retriever (local fallback when Supabase is unavailable)."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

import chromadb

from mcp_server.domain.interfaces import IVectorRetriever
from mcp_server.domain.invariants import require_positive_int
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter
from mcp_server.infrastructure.retrieval.chunk_hit_mapping import row_to_chunk_hit


def _chroma_where(filters: ChunkRetrievalFilter) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if filters.course_id is not None:
        clauses.append({"course_id": filters.course_id})
    if filters.language is not None:
        clauses.append({"language": filters.language})
    if filters.tags:
        for tag in filters.tags:
            clauses.append({"tags": {"$contains": tag}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _distance_to_score(distance: float) -> float:
    """Convert Chroma distance (lower is better) to a bounded similarity score."""
    return 1.0 / (1.0 + max(distance, 0.0))


class ChromaVectorRetriever(IVectorRetriever):
    """Retrieve chunks from a local persistent Chroma collection.

    Hybrid mode degrades to vector search — Chroma has no Postgres ``tsvector`` FTS.
    """

    def __init__(
        self,
        persist_path: str,
        collection_name: str = "document_chunks",
    ) -> None:
        self._persist_path = persist_path
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: chromadb.Collection | None = None

    def _collection_or_create(self) -> chromadb.Collection:
        if self._collection is None:
            self._client = chromadb.PersistentClient(path=self._persist_path)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

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
        _ = mode, query_text
        return await asyncio.to_thread(
            self._retrieve_sync,
            query_embedding,
            limit,
            filters,
        )

    def _retrieve_sync(
        self,
        query_embedding: list[float],
        limit: int,
        filters: ChunkRetrievalFilter,
    ) -> list[ChunkHit]:
        collection = self._collection_or_create()
        where = _chroma_where(filters)
        result = collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = cast(list[list[str]], result.get("ids") or [[]])[0]
        documents = cast(list[list[str]], result.get("documents") or [[]])[0]
        metadatas = cast(list[list[dict[str, Any]]], result.get("metadatas") or [[]])[0]
        distances = cast(list[list[float]], result.get("distances") or [[]])[0]

        hits: list[ChunkHit] = []
        for chunk_id, content, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        ):
            meta = metadata or {}
            hits.append(
                row_to_chunk_hit(
                    chunk_id=chunk_id,
                    document_id=str(meta.get("document_id", "")),
                    content=content,
                    score=_distance_to_score(float(distance)),
                    title=meta.get("title"),
                    metadata=meta,
                )
            )
        return hits
