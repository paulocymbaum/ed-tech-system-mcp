"""Core domain entity definitions."""

from typing import Literal

from pydantic import BaseModel, Field


class VideoResult(BaseModel):
    """Normalized educational video search result."""

    title: str
    channel: str
    url: str
    duration_seconds: int | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


class DocumentHit(BaseModel):
    """Document retrieval result from the data repository."""

    id: str
    title: str
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)


class TextChunk(BaseModel):
    """Indexed passage derived from a parent document."""

    id: str | None = None
    document_id: str
    content: str
    content_hash: str
    language: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    chunk_index: int = Field(ge=0)


class ChunkRetrievalFilter(BaseModel):
    """Optional filters applied during vector or hybrid chunk retrieval."""

    course_id: str | None = None
    tags: list[str] | None = None
    language: str | None = None


class ChunkHit(BaseModel):
    """Semantic retrieval unit — may aggregate into DocumentHit for MCP compatibility."""

    id: str
    document_id: str
    title: str | None = None
    content: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)


class GraphEntity(BaseModel):
    """Knowledge-graph entity (Phase B)."""

    id: str
    name: str
    entity_type: str
    metadata: dict[str, str] = Field(default_factory=dict)


class GraphRelation(BaseModel):
    """Knowledge-graph relation (Phase B)."""

    source_id: str
    target_id: str
    relation_type: str
    weight: float = Field(default=1.0, ge=0.0)


RetrievalMode = Literal["vector", "hybrid", "graph"]


class RetrievalResult(BaseModel):
    """Structured output from a RAG retrieval pipeline."""

    chunks: list[ChunkHit]
    entities: list[GraphEntity] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)
    mode: RetrievalMode
