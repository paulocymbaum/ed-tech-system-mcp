"""Pydantic validation schemas for MCP tool I/O (slim — no LangGraph imports)."""

from pydantic import BaseModel, Field, field_validator

from mcp_server.domain.input_safety import require_safe_user_text
from mcp_server.domain.schemas import VideoResult


class VideoSearchRequest(BaseModel):
    """Validated input for video search tool calls."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)
    language: str = Field(default="en", min_length=2, max_length=10)
    safe_search: bool = True

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class VideoSearchResponse(BaseModel):
    """Validated output for video search tool calls."""

    videos: list[VideoResult]


class WebSearchRequest(BaseModel):
    """Validated input for web search tool calls."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class WebSearchResponse(BaseModel):
    """Validated output for web search tool calls."""

    results: list[str]

