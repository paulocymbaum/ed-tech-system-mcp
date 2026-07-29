"""Tests for vector store backend resolution."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcp_server.infrastructure.retrieval.vector_store_backend import resolve_vector_store_backend


@dataclass
class _Settings:
    vector_store_backend: str
    supabase_vector_enabled: bool


def test_auto_defaults_to_chroma_when_supabase_vector_disabled() -> None:
    settings = _Settings(vector_store_backend="auto", supabase_vector_enabled=False)
    assert resolve_vector_store_backend(settings) == "chroma"


def test_auto_uses_supabase_when_vector_enabled() -> None:
    settings = _Settings(vector_store_backend="auto", supabase_vector_enabled=True)
    assert resolve_vector_store_backend(settings) == "supabase"


def test_explicit_chroma_backend() -> None:
    settings = _Settings(vector_store_backend="chroma", supabase_vector_enabled=True)
    assert resolve_vector_store_backend(settings) == "chroma"


def test_explicit_supabase_backend() -> None:
    settings = _Settings(vector_store_backend="supabase", supabase_vector_enabled=False)
    assert resolve_vector_store_backend(settings) == "supabase"


def test_invalid_backend_raises() -> None:
    settings = _Settings(vector_store_backend="pinecone", supabase_vector_enabled=False)
    with pytest.raises(ValueError, match="VECTOR_STORE_BACKEND"):
        resolve_vector_store_backend(settings)
