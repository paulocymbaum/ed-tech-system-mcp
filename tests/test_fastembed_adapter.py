"""Infrastructure behavior tests for FastEmbedAdapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.infrastructure.embeddings.fastembed_adapter import FastEmbedAdapter


@pytest.mark.asyncio
async def test_T22_fastembed_adapter_creates_cache_dir_before_model_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "nested" / "embed-cache"
    assert not cache_dir.exists()

    class _FakeTextEmbedding:
        def __init__(self, *, model_name: str, cache_dir: str) -> None:
            if not Path(cache_dir).is_dir():
                raise OSError(f"cache dir missing: {cache_dir}")

        def embed(self, texts: list[str]):
            return iter([[0.0] * 384 for _ in texts])

    adapter = FastEmbedAdapter(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        dimensions=384,
        cache_dir=str(cache_dir),
    )

    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", _FakeTextEmbedding)

    vectors = await adapter.embed_queries(["hello"])

    assert cache_dir.is_dir()
    assert len(vectors) == 1
    assert len(vectors[0]) == 384
