"""Supabase vector index writer for document chunks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from supabase import Client, create_client

from mcp_server.domain.interfaces import IVectorIndexWriter
from mcp_server.domain.invariants import require_credential
from mcp_server.domain.schemas import TextChunk

_UPSERT_BATCH_SIZE = 100


class SupabaseVectorIndexWriter(IVectorIndexWriter):
    """Upsert chunks and embeddings into Supabase ``document_chunks``."""

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

    async def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        content: str,
        content_hash: str,
        course_id: str | None = None,
        language: str | None = None,
    ) -> None:
        """Upsert the parent ``documents`` row required by ``document_chunks`` FK."""
        client = self._client_or_create()
        row: dict[str, Any] = {
            "id": document_id,
            "title": title,
            "content": content,
            "content_hash": content_hash,
            "language": language,
        }
        if course_id is not None:
            row["course_id"] = course_id
        await asyncio.to_thread(
            lambda: client.table("documents").upsert(row, on_conflict="id").execute(),
        )

    async def get_document_content_hash(self, document_id: str) -> str | None:
        client = self._client_or_create()

        def _fetch() -> str | None:
            response = (
                client.table("documents")
                .select("content_hash")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if not rows:
                return None
            raw_hash = rows[0].get("content_hash")
            return str(raw_hash) if raw_hash else None

        return await asyncio.to_thread(_fetch)

    async def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            msg = "chunks and embeddings length mismatch"
            raise ValueError(msg)
        if not chunks:
            return

        client = self._client_or_create()
        rows: list[dict[str, Any]] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            rows.append(
                {
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "language": chunk.language,
                    "chunk_index": chunk.chunk_index,
                    "metadata": chunk.metadata,
                    "embedding": embedding,
                    "deleted_at": None,
                }
            )

        await asyncio.to_thread(self._upsert_rows, client, rows)

    def _upsert_rows(self, client: Client, rows: list[dict[str, Any]]) -> None:
        for offset in range(0, len(rows), _UPSERT_BATCH_SIZE):
            batch = rows[offset : offset + _UPSERT_BATCH_SIZE]
            client.table("document_chunks").upsert(
                batch,
                on_conflict="document_id,chunk_index,content_hash",
            ).execute()

    async def delete_by_document_id(self, document_id: str) -> None:
        client = self._client_or_create()
        deleted_at = datetime.now(UTC).isoformat()
        await asyncio.to_thread(
            lambda: (
                client.table("document_chunks")
                .update({"deleted_at": deleted_at})
                .eq("document_id", document_id)
                .execute()
            ),
        )
