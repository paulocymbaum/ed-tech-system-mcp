"""Pydantic validation schemas for MCP tool I/O."""

from pydantic import BaseModel, Field

from mcp_server.domain.schemas import VideoResult


class VideoSearchRequest(BaseModel):
    """Validated input for video search tool calls."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)
    language: str = Field(default="en", min_length=2, max_length=10)
    safe_search: bool = True


class VideoSearchResponse(BaseModel):
    """Validated output for video search tool calls."""

    videos: list[VideoResult]
