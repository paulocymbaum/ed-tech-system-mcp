"""Resolve which vector-store backend to use for RAG retrieval and ingest."""

from __future__ import annotations

from typing import Literal, Protocol

VectorStoreBackend = Literal["supabase", "chroma"]


class VectorStoreSettings(Protocol):
    """Settings subset required to pick a vector store backend."""

    vector_store_backend: str
    supabase_vector_enabled: bool


def resolve_vector_store_backend(settings: VectorStoreSettings) -> VectorStoreBackend:
    """Return ``chroma`` or ``supabase`` based on explicit or auto configuration."""
    backend = settings.vector_store_backend.strip().lower()
    if backend == "chroma":
        return "chroma"
    if backend == "supabase":
        return "supabase"
    if backend != "auto":
        msg = f"VECTOR_STORE_BACKEND must be 'auto', 'supabase', or 'chroma', got {backend!r}"
        raise ValueError(msg)
    if settings.supabase_vector_enabled:
        return "supabase"
    return "chroma"
