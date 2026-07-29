"""Indexing helpers for the RAG validation workflow."""

from __future__ import annotations

from mcp_server.domain.interfaces import IEmbeddingProvider, IVectorIndexWriter

_DEFAULT_EMBED_BATCH_SIZE = 32


async def embed_passages_in_batches(
    embedder: IEmbeddingProvider,
    texts: list[str],
    *,
    batch_size: int = _DEFAULT_EMBED_BATCH_SIZE,
) -> list[list[float]]:
    """Embed passages in bounded batches to reduce peak memory and wall time."""
    if not texts:
        return []
    if batch_size < 1:
        msg = "batch_size must be at least 1"
        raise ValueError(msg)

    vectors: list[list[float]] = []
    for offset in range(0, len(texts), batch_size):
        batch = texts[offset : offset + batch_size]
        vectors.extend(await embedder.embed_passages(batch))
    if len(vectors) != len(texts):
        msg = "Embedding provider returned an unexpected vector count"
        raise RuntimeError(msg)
    return vectors


async def resolve_indexed_content_hash(
    writer: IVectorIndexWriter,
    document_id: str,
) -> str | None:
    """Return the stored parent-document content hash when the writer supports lookups."""
    getter = getattr(writer, "get_document_content_hash", None)
    if not callable(getter):
        return None
    result = getter(document_id)
    if hasattr(result, "__await__"):
        indexed_hash = await result
    else:
        indexed_hash = result
    return str(indexed_hash) if indexed_hash else None
