"""ChromaDB vector index writer (local fallback when Supabase is unavailable)."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import chromadb

from mcp_server.domain.interfaces import IVectorIndexWriter
from mcp_server.domain.schemas import TextChunk

_DOCUMENTS_COLLECTION = "documents"


def _chunk_id(chunk: TextChunk) -> str:
    return f"{chunk.document_id}:{chunk.chunk_index}:{chunk.content_hash}"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class ChromaVectorIndexWriter(IVectorIndexWriter):
    """Upsert chunks and parent document metadata into local persistent Chroma."""

    def __init__(
        self,
        persist_path: str,
        collection_name: str = "document_chunks",
    ) -> None:
        self._persist_path = persist_path
        self._collection_name = collection_name
        self._client: Any = None

    def _client_or_create(self) -> Any:
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self._persist_path)
        return self._client

    def _chunks_collection(self) -> Any:
        client = self._client_or_create()
        return client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _documents_collection(self) -> Any:
        client = self._client_or_create()
        return client.get_or_create_collection(name=_DOCUMENTS_COLLECTION)

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
        """Upsert parent document metadata for ingest parity with Supabase."""
        await asyncio.to_thread(
            self._upsert_document_sync,
            document_id,
            title,
            content,
            content_hash,
            course_id,
            language,
        )

    def _upsert_document_sync(
        self,
        document_id: str,
        title: str,
        content: str,
        content_hash: str,
        course_id: str | None,
        language: str | None,
    ) -> None:
        collection = self._documents_collection()
        metadata: dict[str, Any] = {
            "title": title,
            "content_hash": content_hash,
        }
        if course_id is not None:
            metadata["course_id"] = course_id
        if language is not None:
            metadata["language"] = language
        collection.upsert(
            ids=[document_id],
            documents=[content],
            metadatas=[metadata],
        )

    async def get_document_content_hash(self, document_id: str) -> str | None:
        return await asyncio.to_thread(self._get_document_content_hash_sync, document_id)

    def _get_document_content_hash_sync(self, document_id: str) -> str | None:
        collection = self._documents_collection()
        result = collection.get(ids=[document_id], include=["metadatas"])
        ids = result.get("ids") or []
        if not ids:
            return None
        metadatas = result.get("metadatas") or []
        if not metadatas:
            return None
        metadata = metadatas[0] or {}
        raw_hash = metadata.get("content_hash")
        return str(raw_hash) if raw_hash else None

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
        await asyncio.to_thread(self._upsert_chunks_sync, chunks, embeddings)

    def _upsert_chunks_sync(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        collection = self._chunks_collection()
        document_ids = {chunk.document_id for chunk in chunks}
        for document_id in document_ids:
            self._delete_document_chunks_sync(collection, document_id)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            ids.append(_chunk_id(chunk))
            documents.append(chunk.content)
            meta = dict(chunk.metadata)
            meta.update(
                {
                    "document_id": chunk.document_id,
                    "chunk_index": str(chunk.chunk_index),
                    "content_hash": chunk.content_hash,
                }
            )
            if chunk.language is not None:
                meta["language"] = chunk.language
            metadatas.append(meta)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def delete_by_document_id(self, document_id: str) -> None:
        await asyncio.to_thread(self._delete_by_document_id_sync, document_id)

    def _delete_by_document_id_sync(self, document_id: str) -> None:
        collection = self._chunks_collection()
        self._delete_document_chunks_sync(collection, document_id)

    def _delete_document_chunks_sync(
        self,
        collection: Any,
        document_id: str,
    ) -> None:
        existing = collection.get(where={"document_id": document_id}, include=[])
        ids = existing.get("ids") or []
        if ids:
            collection.delete(ids=ids)
