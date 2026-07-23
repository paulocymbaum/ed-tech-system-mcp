"""LangGraph nodes for the RAG validation workflow."""

from __future__ import annotations

import hashlib
import time

from mcp_server.application.agents.rag_retrieval.nodes import route_after_retrieve
from mcp_server.application.agents.rag_validation.fixture import (
    FIXTURE_DOCUMENT_ID,
    FIXTURE_TITLE,
    load_expected_phrases,
    resolve_document_text,
)
from mcp_server.application.agents.rag_validation.indexing import (
    embed_passages_in_batches,
    resolve_indexed_content_hash,
)
from mcp_server.application.agents.rag_validation.state import RagValidationState
from mcp_server.application.retrieval_runtime import (
    get_chunking_strategy,
    get_embedding_provider,
    get_vector_index_writer,
)
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.rag_benchmarks import (
    build_rag_evaluation_context,
    compute_rag_benchmarks,
    partition_phrase_matches,
)

__all__ = ["load_document", "index_document", "validate_retrieval", "route_after_retrieve"]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


async def load_document(state: RagValidationState) -> dict[str, object]:
    """Resolve document text from inline UI input or the bundled fixture file."""
    try:
        text, source = resolve_document_text(
            state.get("document_text"),
            fixture_path=state.get("fixture_path"),
        )
    except FileNotFoundError as exc:
        raise ResourceNotFoundError(str(exc)) from exc

    if not text.strip():
        raise ResourceNotFoundError("Document text is empty")

    title = (state.get("document_title") or FIXTURE_TITLE).strip() or FIXTURE_TITLE
    return {
        "document_text": text,
        "document_title": title,
        "document_source": source,
        "content_hash": _content_hash(text),
    }


async def index_document(state: RagValidationState) -> dict[str, object]:
    """Chunk, embed, and upsert the loaded document into the vector index."""
    started = time.perf_counter()
    chunking = get_chunking_strategy()
    embedder = get_embedding_provider()
    writer = get_vector_index_writer()
    if chunking is None:
        raise ResourceNotFoundError("Chunking strategy has not been initialized")
    if embedder is None:
        raise ResourceNotFoundError("Embedding provider has not been initialized")
    if writer is None:
        raise ResourceNotFoundError("Vector index writer has not been initialized")

    text = state.get("document_text")
    if text is None or not text.strip():
        raise ResourceNotFoundError("document_text is required before index_document")

    title = state.get("document_title") or FIXTURE_TITLE
    content_hash = _content_hash(text)
    language = state.get("language")
    course_id = state.get("course_id")
    metadata: dict[str, str] = {"title": title}
    if course_id is not None:
        metadata["course_id"] = course_id

    chunks = chunking.chunk(
        text,
        document_id=FIXTURE_DOCUMENT_ID,
        language=language,
        metadata=metadata,
    )
    if not chunks:
        msg = "Document produced no chunks to index"
        raise ResourceNotFoundError(msg)

    indexed_hash = await resolve_indexed_content_hash(writer, FIXTURE_DOCUMENT_ID)
    if indexed_hash == content_hash:
        latency_ms = int((time.perf_counter() - started) * 1000)
        chunk_size = getattr(chunking, "chunk_size", None)
        chunk_overlap = getattr(chunking, "chunk_overlap", None)
        return {
            "index_complete": True,
            "index_skipped": True,
            "indexed_chunk_count": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "latency_ms": latency_ms,
        }

    upsert_document = getattr(writer, "upsert_document", None)
    if callable(upsert_document):
        await upsert_document(
            document_id=FIXTURE_DOCUMENT_ID,
            title=title,
            content=text,
            content_hash=content_hash,
            course_id=course_id,
            language=language,
        )

    embeddings = await embed_passages_in_batches(
        embedder,
        [chunk.content for chunk in chunks],
    )
    await writer.upsert_chunks(chunks, embeddings)

    latency_ms = int((time.perf_counter() - started) * 1000)
    chunk_size = getattr(chunking, "chunk_size", None)
    chunk_overlap = getattr(chunking, "chunk_overlap", None)
    return {
        "index_complete": True,
        "index_skipped": False,
        "indexed_chunk_count": len(chunks),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "latency_ms": latency_ms,
    }


async def validate_retrieval(state: RagValidationState) -> dict[str, object]:
    """Assert expected phrases appear in retrieved chunks."""
    expected = load_expected_phrases(state.get("expected_phrases"))
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])
    merged = state.get("merged_context", "")
    benchmarks = compute_rag_benchmarks(
        expected_phrases=expected,
        chunks=chunks,
        merged_context=merged,
    )
    matched_phrases, missing = partition_phrase_matches(
        expected,
        chunks=chunks,
        merged_context=merged,
    )
    passed = not missing
    validation_errors = [f"Missing expected phrase: {phrase}" for phrase in missing]
    if not chunks and state.get("index_complete"):
        validation_errors = [
            "Retrieval returned no chunks after indexing — check vector store wiring and embeddings.",
            *validation_errors,
        ]
    elif missing and chunks:
        validation_errors = [
            *validation_errors,
            (
                f"Retrieved {len(chunks)} chunk(s) at effective k="
                f"{state.get('rag_evaluation_context', {}).get('effective_k', len(chunks))} "
                "but expected phrases were missing — try raising retrieve limit or rerank top n."
            ),
        ]
    evaluation_context = build_rag_evaluation_context(
        retrieval_mode=state["retrieval_mode"],
        retrieve_limit=state["retrieve_limit"],
        rerank_enabled=state["rerank_enabled"],
        rerank_top_n=state["rerank_top_n"],
        chunks=chunks,
        rerank_applied=bool(state.get("rerank_applied")),
        hybrid_fts_active=bool(state.get("hybrid_fts_active")),
        chunk_size=state.get("chunk_size"),
        chunk_overlap=state.get("chunk_overlap"),
        indexed_chunk_count=state.get("indexed_chunk_count"),
    )
    return {
        "validation_passed": passed,
        "validation_errors": validation_errors,
        "expected_phrases": expected,
        "matched_phrases": matched_phrases,
        "missing_phrases": missing,
        "rag_benchmarks": benchmarks.as_dict(),
        "rag_evaluation_context": evaluation_context.as_dict(),
    }
