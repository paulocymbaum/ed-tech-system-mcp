"""Core domain entity definitions."""

from pydantic import BaseModel, Field


class VideoResult(BaseModel):
    """Normalized educational video search result."""

    title: str
    channel: str
    url: str
    duration_seconds: int | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)


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
