"""Domain entity contract tests (T01–T06)."""

import pytest
from pydantic import ValidationError

from mcp_server.domain.cache import DEFAULT_CACHE_RULES, CacheOperationType
from mcp_server.domain.schemas import (
    ChunkHit,
    ChunkRetrievalFilter,
    DocumentHit,
    GraphEntity,
    GraphRelation,
    RetrievalResult,
    TextChunk,
    VideoResult,
)


def test_t01_video_result_happy_path() -> None:
    result = VideoResult(
        title="Intro to Algebra",
        channel="Math Academy",
        url="https://example.com/video",
    )
    assert result.title == "Intro to Algebra"
    assert result.channel == "Math Academy"
    assert result.url == "https://example.com/video"


def test_t02_video_result_default_relevance_score() -> None:
    result = VideoResult(title="T", channel="C", url="https://example.com")
    assert result.relevance_score == 0.0


def test_t03_video_result_relevance_score_bounds() -> None:
    with pytest.raises(ValidationError):
        VideoResult(title="T", channel="C", url="https://example.com", relevance_score=-0.1)
    with pytest.raises(ValidationError):
        VideoResult(title="T", channel="C", url="https://example.com", relevance_score=1.1)


def test_t04_video_result_optional_duration() -> None:
    result = VideoResult(title="T", channel="C", url="https://example.com")
    assert result.duration_seconds is None


def test_t05_document_hit_happy_path() -> None:
    hit = DocumentHit(id="doc-1", title="Lesson 1", content="Body text")
    assert hit.id == "doc-1"
    assert hit.title == "Lesson 1"
    assert hit.content == "Body text"


def test_t06_document_hit_metadata_defaults_empty() -> None:
    hit = DocumentHit(id="doc-1", title="Lesson 1", content="Body text")
    assert hit.metadata == {}


def test_t_rag01_text_chunk_happy_path() -> None:
    chunk = TextChunk(
        document_id="doc-1",
        content="Lesson body",
        content_hash="abc123",
        chunk_index=0,
        language="en",
    )
    assert chunk.document_id == "doc-1"
    assert chunk.chunk_index == 0
    assert chunk.language == "en"


def test_t_rag02_chunk_hit_score_defaults() -> None:
    hit = ChunkHit(id="chunk-1", document_id="doc-1", content="Passage text")
    assert hit.score == 0.0


def test_t_rag03_chunk_retrieval_filter_optional_fields() -> None:
    filters = ChunkRetrievalFilter()
    assert filters.course_id is None
    assert filters.tags is None
    assert filters.language is None


def test_t_rag04_retrieval_result_happy_path() -> None:
    chunk = ChunkHit(id="chunk-1", document_id="doc-1", content="Passage", score=0.8)
    result = RetrievalResult(chunks=[chunk], mode="hybrid")
    assert len(result.chunks) == 1
    assert result.mode == "hybrid"
    assert result.entities == []
    assert result.relations == []


def test_t_rag05_graph_entity_relation_defaults() -> None:
    entity = GraphEntity(id="e-1", name="Photosynthesis", entity_type="concept")
    relation = GraphRelation(source_id="e-1", target_id="e-2", relation_type="requires")
    assert entity.metadata == {}
    assert relation.weight == 1.0


def test_t_rag06_text_chunk_negative_index_rejected() -> None:
    with pytest.raises(ValidationError):
        TextChunk(
            document_id="doc-1",
            content="Body",
            content_hash="hash",
            chunk_index=-1,
        )


def test_t_rag07_chunk_hit_score_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        ChunkHit(id="1", document_id="d", content="x", score=-0.1)
    with pytest.raises(ValidationError):
        ChunkHit(id="1", document_id="d", content="x", score=1.1)


def test_t_rag08_default_cache_rules_include_rag_operations() -> None:
    embedding_rule = DEFAULT_CACHE_RULES[CacheOperationType.EMBEDDING_QUERY]
    vector_rule = DEFAULT_CACHE_RULES[CacheOperationType.VECTOR_RETRIEVE]
    assert embedding_rule.key_prefix == "embed"
    assert vector_rule.key_prefix == "vector"
