"""MCP tool wrappers around application workflows.

Changelog: changelog/2026-07-21/interface/IMPLEMENTATION1.md (BL-006, BL-013, BL-011)
Changelog: changelog/2026-07-21/infrastructure/IMPLEMENTATION3.md (BL-019)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from mcp_server.application.lesson_enrichment import (
    LessonEnrichmentQuery,
)
from mcp_server.application.lesson_enrichment import (
    build_lesson_enrichment_query as run_build_lesson_enrichment_query,
)
from mcp_server.application.mcp_tool_cache_runtime import get_mcp_tool_cache
from mcp_server.application.search_services import search_videos, search_web_snippets
from mcp_server.domain.exceptions import DomainError
from mcp_server.interface.error_mapping import raise_as_mcp_error
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation import (
    VideoSearchRequest,
    VideoSearchResponse,
    WebSearchRequest,
    WebSearchResponse,
)

logger = logging.getLogger(__name__)

# Re-export for tests and catalog docs that still name the MCP response type.
BuildLessonEnrichmentQueryResponse = LessonEnrichmentQuery


async def _invoke_health_check() -> str:
    return "ok"


async def _invoke_search_youtube(request: VideoSearchRequest) -> VideoSearchResponse:
    videos = await search_videos(
        request.query,
        max_results=request.max_results,
        language=request.language,
        safe_search=request.safe_search,
    )
    return VideoSearchResponse(videos=videos)


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


async def _invoke_search_web(request: WebSearchRequest) -> WebSearchResponse:
    results = await search_web_snippets(request.query, max_results=request.max_results)
    return WebSearchResponse(results=results)


@mcp.tool
async def search_web(
    query: str,
    max_results: int = 5,
) -> WebSearchResponse:
    """Search the web for relevant snippets matching a query."""
    request = WebSearchRequest(query=query, max_results=max_results)
    args = request.model_dump()
    return await _cached_tool_invoke(
        "search_web",
        args,
        lambda: _invoke_search_web(request),
    )


@mcp.tool
async def build_lesson_enrichment_query(
    course_title: str,
    module_title: str,
    lesson_title: str,
) -> LessonEnrichmentQuery:
    """Build a 4-5 term search query for lesson enrichment from course/module/lesson titles."""
    args = {
        "course_title": course_title,
        "module_title": module_title,
        "lesson_title": lesson_title,
    }
    return await _cached_tool_invoke(
        "build_lesson_enrichment_query",
        args,
        lambda: run_build_lesson_enrichment_query(
            course_title,
            module_title,
            lesson_title,
        ),
    )
