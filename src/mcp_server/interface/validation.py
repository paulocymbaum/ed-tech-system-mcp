"""Pydantic validation schemas for MCP tool I/O."""

from pydantic import BaseModel, Field

from mcp_server.application.agent import DocumentVideoState
from mcp_server.domain.schemas import DocumentHit, VideoResult


class DocumentSummary(BaseModel):
    """Pruned document payload for MCP JSON-RPC responses."""

    id: str
    title: str
    snippet: str


class DocumentQueryRequest(BaseModel):
    """Validated input for document + video discovery tool calls."""

    query: str = Field(min_length=1)
    document_limit: int = Field(default=10, ge=1, le=50)
    video_limit: int = Field(default=5, ge=1, le=25)


class DocumentQueryResponse(BaseModel):
    """Validated output for document + video discovery tool calls."""

    documents: list[DocumentSummary]
    videos: list[VideoResult]


class VideoSearchRequest(BaseModel):
    """Validated input for video search tool calls."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)
    language: str = Field(default="en", min_length=2, max_length=10)
    safe_search: bool = True


class VideoSearchResponse(BaseModel):
    """Validated output for video search tool calls."""

    videos: list[VideoResult]


class WorkflowRunRequest(BaseModel):
    """Validated input for LangGraph workflow execution."""

    query: str = Field(min_length=1)
    document_limit: int = Field(default=10, ge=1, le=50)
    video_limit: int = Field(default=5, ge=1, le=25)


class WorkflowRunResponse(BaseModel):
    """Validated output for LangGraph workflow execution."""

    query: str
    search_terms: str
    document_count: int = Field(ge=0)
    video_count: int = Field(ge=0)
    documents: list[DocumentSummary]
    videos: list[VideoResult]


def document_hit_to_summary(hit: DocumentHit, *, snippet_max_len: int = 200) -> DocumentSummary:
    """Map a domain document hit to a pruned MCP response DTO."""
    content = hit.content
    if len(content) <= snippet_max_len:
        snippet = content
    else:
        snippet = f"{content[:snippet_max_len]}..."
    return DocumentSummary(id=hit.id, title=hit.title, snippet=snippet)


def document_hits_to_summaries(
    hits: list[DocumentHit],
    *,
    snippet_max_len: int = 200,
) -> list[DocumentSummary]:
    """Map domain document hits to pruned MCP summaries."""
    return [document_hit_to_summary(hit, snippet_max_len=snippet_max_len) for hit in hits]


def workflow_state_to_run_response(state: DocumentVideoState) -> WorkflowRunResponse:
    """Map a document-video graph state to the MCP/local UI workflow response."""
    documents = state.get("documents", [])
    videos = state.get("videos", [])
    return WorkflowRunResponse(
        query=state["query"],
        search_terms=state["search_terms"],
        document_count=state["document_count"],
        video_count=state["video_count"],
        documents=document_hits_to_summaries(documents),
        videos=videos,
    )
