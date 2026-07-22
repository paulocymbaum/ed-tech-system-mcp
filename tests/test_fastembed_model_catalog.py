"""Tests for fastembed model resolution."""

from __future__ import annotations

from mcp_server.infrastructure.embeddings.fastembed_model_catalog import resolve_embedding_model


def test_e5_small_alias_resolves_to_supported_multilingual_model() -> None:
    resolved = resolve_embedding_model("intfloat/multilingual-e5-small", dimensions=384)

    assert resolved.model_name == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert resolved.dimensions == 384
    assert resolved.use_e5_prefixes is False
    assert resolved.requested_model == "intfloat/multilingual-e5-small"


def test_e5_large_keeps_prefix_contract() -> None:
    resolved = resolve_embedding_model("intfloat/multilingual-e5-large", dimensions=1024)

    assert resolved.model_name == "intfloat/multilingual-e5-large"
    assert resolved.dimensions == 1024
    assert resolved.use_e5_prefixes is True
