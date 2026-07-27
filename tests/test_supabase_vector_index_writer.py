"""Tests for SupabaseVectorIndexWriter upsert contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_server.domain.schemas import TextChunk
from mcp_server.infrastructure.retrieval.supabase_vector_index_writer import (
    SupabaseVectorIndexWriter,
)


@pytest.mark.asyncio
async def test_upsert_document_calls_documents_table() -> None:
    client = MagicMock()
    writer = SupabaseVectorIndexWriter("https://test.supabase.co", "service-key")

    with patch(
        "mcp_server.infrastructure.retrieval.supabase_vector_index_writer.create_client",
        return_value=client,
    ):
        await writer.upsert_document(
            document_id="11111111-1111-1111-1111-111111111111",
            title="Photosynthesis",
            content="Plants convert light to energy.",
            content_hash="abc123",
            course_id="bio-101",
            language="en",
        )

    client.table.assert_called_with("documents")
    client.table.return_value.upsert.assert_called_once_with(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "title": "Photosynthesis",
            "content": "Plants convert light to energy.",
            "content_hash": "abc123",
            "language": "en",
            "course_id": "bio-101",
        },
        on_conflict="id",
    )


@pytest.mark.asyncio
async def test_upsert_chunks_length_mismatch_raises() -> None:
    writer = SupabaseVectorIndexWriter("https://test.supabase.co", "service-key")
    chunks = [
        TextChunk(
            document_id="doc-1",
            content="chunk",
            content_hash="hash",
            chunk_index=0,
        )
    ]

    with pytest.raises(ValueError, match="length mismatch"):
        await writer.upsert_chunks(chunks, [[0.1] * 384, [0.2] * 384])
