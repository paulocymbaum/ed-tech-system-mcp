"""State for the RAG validation LangGraph workflow."""

from __future__ import annotations

from typing import NotRequired

from mcp_server.application.agents.rag_retrieval.state import RagRetrievalState


class RagValidationState(RagRetrievalState, total=False):
    """Load document → index → RAG pipeline → assert expected phrases in context."""

    fixture_path: NotRequired[str]
    document_text: NotRequired[str]
    document_title: NotRequired[str]
    document_source: NotRequired[str]
    expected_phrases: NotRequired[list[str]]
    indexed_chunk_count: NotRequired[int]
    index_complete: NotRequired[bool]
    index_skipped: NotRequired[bool]
    validation_passed: NotRequired[bool]
    validation_errors: NotRequired[list[str]]
    rag_benchmarks: NotRequired[dict[str, float | int]]
    rag_evaluation_context: NotRequired[dict[str, str | int | bool | None]]
    matched_phrases: NotRequired[list[str]]
    missing_phrases: NotRequired[list[str]]
    chunk_size: NotRequired[int]
    chunk_overlap: NotRequired[int]
