"""Tests for SupabasePgvectorRetriever RPC routing and row mapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.domain.schemas import ChunkRetrievalFilter
from mcp_server.infrastructure.retrieval.supabase_vector_retriever import SupabasePgvectorRetriever


def _sample_row() -> dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "document_id": "22222222-2222-2222-2222-222222222222",
        "title": "Photosynthesis",
        "content": "Plants convert light to energy.",
        "score": 1.25,
        "metadata": {"section": "intro"},
    }


def _mock_client(rows: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.data = rows
    client.rpc.return_value.execute.return_value = response
    return client


@pytest.mark.asyncio
async def test_vector_mode_calls_match_chunks_rpc() -> None:
    client = _mock_client([_sample_row()])
    retriever = SupabasePgvectorRetriever("https://test.supabase.co", "service-key")

    with patch(
        "mcp_server.infrastructure.retrieval.supabase_vector_retriever.create_client",
        return_value=client,
    ):
        hits = await retriever.retrieve(
            [0.1] * 384,
            limit=5,
            filters=ChunkRetrievalFilter(),
            mode="vector",
        )

    client.rpc.assert_called_once_with(
        "match_chunks",
        {
            "query_embedding": [0.1] * 384,
            "match_count": 5,
            "filter": {},
        },
    )
    assert len(hits) == 1
    assert hits[0].title == "Photosynthesis"
    assert hits[0].score == 1.0
    assert hits[0].metadata == {"section": "intro"}


@pytest.mark.asyncio
async def test_hybrid_mode_calls_hybrid_search_rpc() -> None:
    client = _mock_client([_sample_row()])
    retriever = SupabasePgvectorRetriever("https://test.supabase.co", "service-key")
    filters = ChunkRetrievalFilter(course_id="bio-101", language="en", tags=["plants"])

    with patch(
        "mcp_server.infrastructure.retrieval.supabase_vector_retriever.create_client",
        return_value=client,
    ):
        hits = await retriever.retrieve(
            [0.2] * 384,
            limit=10,
            filters=filters,
            mode="hybrid",
            query_text="how plants make energy",
        )

    client.rpc.assert_called_once_with(
        "hybrid_search_chunks",
        {
            "query_text": "how plants make energy",
            "query_embedding": [0.2] * 384,
            "match_count": 10,
            "filter": {
                "course_id": "bio-101",
                "language": "en",
                "tags": ["plants"],
            },
        },
    )
    assert hits[0].document_id == "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_hybrid_mode_requires_query_text() -> None:
    retriever = SupabasePgvectorRetriever("https://test.supabase.co", "service-key")

    with (
        patch(
            "mcp_server.infrastructure.retrieval.supabase_vector_retriever.create_client",
            return_value=_mock_client([]),
        ),
        pytest.raises(ValueError, match="query_text is required"),
    ):
        await retriever.retrieve(
            [0.1] * 384,
            limit=5,
            filters=ChunkRetrievalFilter(),
            mode="hybrid",
            query_text=None,
        )
