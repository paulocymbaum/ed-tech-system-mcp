"""Core domain entity definitions."""

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
