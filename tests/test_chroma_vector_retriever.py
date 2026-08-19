"""Tests for ChromaVectorRetriever query mapping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_server.domain.exceptions import DomainValidationError
from mcp_server.domain.schemas import ChunkRetrievalFilter
from mcp_server.infrastructure.retrieval.chroma_vector_retriever import ChromaVectorRetriever


def _mock_collection() -> MagicMock:
    collection = MagicMock()
    collection.query.return_value = {
        "ids": [["doc:0:abc"]],
        "documents": [["Plants convert light to energy."]],
        "metadatas": [[{"document_id": "doc-1", "title": "Biology", "chunk_index": 0}]],
        "distances": [[0.25]],
    }
    return collection


@pytest.mark.asyncio
async def test_chroma_retriever_maps_query_results() -> None:
    collection = _mock_collection()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    retriever = ChromaVectorRetriever(persist_path="/tmp/chroma-test")

    with patch(
        "mcp_server.infrastructure.retrieval.chroma_vector_retriever.chromadb.PersistentClient",
        return_value=client,
    ):
        hits = await retriever.retrieve(
            [0.1] * 384,
            limit=5,
            filters=ChunkRetrievalFilter(
                tenant_id="8d9cad71-55db-43e4-87f3-89b9077c174f",
                course_id="bio-101",
            ),
            mode="vector",
        )

    collection.query.assert_called_once()
    call_kwargs = collection.query.call_args.kwargs
    assert call_kwargs["n_results"] == 5
    assert call_kwargs["where"] == {
        "$and": [
            {"tenant_id": "8d9cad71-55db-43e4-87f3-89b9077c174f"},
            {"course_id": "bio-101"},
        ]
    }
    assert len(hits) == 1
    assert hits[0].document_id == "doc-1"
    assert hits[0].title == "Biology"
    assert hits[0].score > 0.0


@pytest.mark.asyncio
async def test_chroma_hybrid_mode_uses_vector_search() -> None:
    collection = _mock_collection()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    retriever = ChromaVectorRetriever(persist_path="/tmp/chroma-test")

    with patch(
        "mcp_server.infrastructure.retrieval.chroma_vector_retriever.chromadb.PersistentClient",
        return_value=client,
    ):
        await retriever.retrieve(
            [0.1] * 384,
            limit=3,
            filters=ChunkRetrievalFilter(tenant_id="8d9cad71-55db-43e4-87f3-89b9077c174f"),
            mode="hybrid",
            query_text="photosynthesis",
        )

    collection.query.assert_called_once()
    call_kwargs = collection.query.call_args.kwargs
    assert call_kwargs["where"] == {"tenant_id": "8d9cad71-55db-43e4-87f3-89b9077c174f"}


@pytest.mark.asyncio
async def test_chroma_retriever_requires_tenant_id() -> None:
    retriever = ChromaVectorRetriever(persist_path="/tmp/chroma-test")
    with pytest.raises(DomainValidationError, match="tenant_id is required"):
        await retriever.retrieve(
            [0.1] * 384,
            limit=3,
            filters=ChunkRetrievalFilter(course_id="bio-101"),
            mode="vector",
        )
