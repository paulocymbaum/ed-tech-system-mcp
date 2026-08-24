"""MCP tool wrappers around application workflows.

Changelog: changelog/2026-07-21/interface/IMPLEMENTATION1.md (BL-006, BL-013, BL-011)
Changelog: changelog/2026-07-21/infrastructure/IMPLEMENTATION3.md (BL-019)
Changelog: changelog/2026-07-21/domain/IMPLEMENTATION1.md (BL-009)
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.mcp_tool_cache_runtime import get_mcp_tool_cache
from mcp_server.application.workflow_llm_trace import record_llm_invocation
from mcp_server.application.workflow_runtime import get_document_video_workflow
from mcp_server.domain.exceptions import DomainError, ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity
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

# Search terms should be single words or short phrases without numerals, IDs, or slugs.
_ENRICHMENT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


_WORD_RE = re.compile(r"[a-zA-Z]+")


def _clean_search_words(text: str) -> list[str]:
    """Extract significant, lowercase search words from a title or term.

    Removes numerals, punctuation, and common stop words.
    """
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return [w for w in words if len(w) > 1 and w not in _ENRICHMENT_STOP_WORDS]


def _build_enrichment_terms(
    course_title: str,
    module_title: str,
    lesson_title: str,
    raw_terms: list[str],
) -> list[str]:
    """Build a clean, deduplicated list of 4-5 search terms.

    Terms are sourced from the LLM first, then the course title is appended
    (so it is always represented), and module/lesson titles fill any remaining
    slots up to 5 terms. All numerals and slugs are stripped.
    """
    seen: set[str] = set()
    terms: list[str] = []

    def add_word(word: str) -> None:
        if not word or len(word) < 2 or word in seen or word in _ENRICHMENT_STOP_WORDS:
            return
        seen.add(word)
        terms.append(word)

    for phrase in raw_terms:
        for word in _clean_search_words(phrase):
            add_word(word)

    for word in _clean_search_words(course_title):
        add_word(word)

    for word in _clean_search_words(module_title):
        add_word(word)

    for word in _clean_search_words(lesson_title):
        add_word(word)

    return terms[:5]


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
        course_id=request.course_id,
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
    course_id: str | None = None,
) -> DocumentQueryResponse:
    """Retrieve educational documents enriched with complementary videos."""
    request = DocumentQueryRequest(
        query=query,
        document_limit=document_limit,
        video_limit=video_limit,
        tenant_id=tenant_id,
        course_id=course_id,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "find_documents",
        args,
        lambda: _invoke_find_documents(request),
    )


class BuildLessonEnrichmentQueryResponse(BaseModel):
    """Terms generated from course/module/lesson titles for enrichment search."""

    terms: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=5,
        description="4-5 concise search terms for finding videos and library documents",
    )
    query: str = Field(
        default="",
        description="Terms joined into a single query string for legacy BFFs",
    )


async def _invoke_build_lesson_enrichment_query(
    course_title: str,
    module_title: str,
    lesson_title: str,
) -> BuildLessonEnrichmentQueryResponse:
    """Use a lightweight LLM to turn lesson metadata into 4-5 search terms."""
    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")

    prompt = (
        "You are helping build a search query for lesson enrichment materials "
        "(YouTube videos and educational documents).\n\n"
        f"Course title: {course_title}\n"
        f"Module title: {module_title}\n"
        f"Lesson title: {lesson_title}\n\n"
        "Return a JSON array of 4 to 5 concise, relevant search terms a student would type. "
        "Prefer single lowercase words. Do not include numerals, IDs, slugs, or hyphens. "
        "Include a term for the course name. Avoid repeating terms. "
        "Return ONLY the JSON array, with no markdown or explanation."
    )
    result = await model.ainvoke(
        [HumanMessage(content=prompt)],
        llm_complexity=int(LLMComplexity.LOW),
    )
    raw = result.content if isinstance(result.content, str) else str(result.content)
    record_llm_invocation(
        system_prompt="",
        user_prompt=prompt,
        raw_output=raw,
        model_name=resolve_invoked_model_name(model),
        llm_complexity=int(LLMComplexity.LOW),
    )

    raw_terms: list[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            raw_terms = [str(t).strip() for t in parsed if str(t).strip()]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    terms = _build_enrichment_terms(
        course_title,
        module_title,
        lesson_title,
        raw_terms,
    )

    return BuildLessonEnrichmentQueryResponse(
        terms=terms,
        query=" ".join(terms),
    )


@mcp.tool
async def build_lesson_enrichment_query(
    course_title: str,
    module_title: str,
    lesson_title: str,
) -> BuildLessonEnrichmentQueryResponse:
    """Build a 4-5 term search query for lesson enrichment from course/module/lesson titles."""
    args = {
        "course_title": course_title,
        "module_title": module_title,
        "lesson_title": lesson_title,
    }
    return await _cached_tool_invoke(
        "build_lesson_enrichment_query",
        args,
        lambda: _invoke_build_lesson_enrichment_query(
            course_title,
            module_title,
            lesson_title,
        ),
    )
