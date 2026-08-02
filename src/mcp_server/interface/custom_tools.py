"""MCP tool wrappers around application workflows.

Changelog: changelog/2026-07-21/interface/IMPLEMENTATION1.md (BL-006, BL-013, BL-011)
Changelog: changelog/2026-07-21/infrastructure/IMPLEMENTATION3.md (BL-019)
Changelog: changelog/2026-07-21/domain/IMPLEMENTATION1.md (BL-009)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from mcp_server.application.mcp_tool_cache_runtime import get_mcp_tool_cache
from mcp_server.application.workflow_runtime import get_document_video_workflow
from mcp_server.domain.exceptions import DomainError, ResourceNotFoundError
from mcp_server.interface.error_mapping import raise_as_mcp_error
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    VideoSearchRequest,
    VideoSearchResponse,
    document_hits_to_summaries,
)

logger = logging.getLogger(__name__)


async def _invoke_health_check() -> str:
    return "ok"


async def _invoke_search_youtube(request: VideoSearchRequest) -> VideoSearchResponse:
    workflow = get_document_video_workflow()
    if workflow is None:
        raise ResourceNotFoundError("Document video workflow has not been initialized")
    videos = await workflow.search_videos(
        request.query,
        request.max_results,
        language=request.language,
        safe_search=request.safe_search,
    )
    return VideoSearchResponse(videos=videos)


async def _invoke_find_documents(request: DocumentQueryRequest) -> DocumentQueryResponse:
    workflow = get_document_video_workflow()
    if workflow is None:
        raise ResourceNotFoundError("Document video workflow has not been initialized")
    documents, videos = await workflow.retrieve_with_videos(
        request.query,
        document_limit=request.document_limit,
        video_limit=request.video_limit,
        tenant_id=request.tenant_id,
    )
    return DocumentQueryResponse(
        documents=document_hits_to_summaries(documents),
        videos=videos,
    )


async def _cached_tool_invoke[T](
    tool_name: str,
    args: dict[str, object],
    invoker: Callable[[], Awaitable[T]],
) -> T:
    start = time.perf_counter()
    try:
        tool_cache = get_mcp_tool_cache()
        if tool_cache is None:
            result = await invoker()
        else:
            result = await tool_cache.get_or_invoke(tool_name, args, invoker)
    except DomainError as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "mcp tool tool=%s duration_ms=%.2f outcome=error",
            tool_name,
            duration_ms,
        )
        raise_as_mcp_error(exc)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "mcp tool tool=%s duration_ms=%.2f outcome=error",
            tool_name,
            duration_ms,
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "mcp tool tool=%s duration_ms=%.2f outcome=success",
            tool_name,
            duration_ms,
        )
        return result


@mcp.tool
async def health_check() -> str:
    """Verify the MCP server is running."""
    return await _cached_tool_invoke("health_check", {}, _invoke_health_check)


@mcp.tool
async def search_youtube(
    query: str,
    max_results: int = 5,
    language: str = "en",
    safe_search: bool = True,
) -> VideoSearchResponse:
    """Search for educational YouTube videos matching a query."""
    request = VideoSearchRequest(
        query=query,
        max_results=max_results,
        language=language,
        safe_search=safe_search,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "search_youtube",
        args,
        lambda: _invoke_search_youtube(request),
    )


@mcp.tool
async def find_documents(
    query: str,
    document_limit: int = 10,
    video_limit: int = 5,
    tenant_id: str | None = None,
) -> DocumentQueryResponse:
    """Retrieve educational documents enriched with complementary videos."""
    request = DocumentQueryRequest(
        query=query,
        document_limit=document_limit,
        video_limit=video_limit,
        tenant_id=tenant_id,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "find_documents",
        args,
        lambda: _invoke_find_documents(request),
    )
