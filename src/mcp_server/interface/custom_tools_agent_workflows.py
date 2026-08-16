"""MCP tools for Groq-backed LangGraph workflows (research article, content generation)."""

from __future__ import annotations

from mcp_server.application.agent import ainvoke_with_workflow_timeout
from mcp_server.application.agents.research_article.graph import (
    get_research_article_graph,
    initial_research_article_state,
)
from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation_workflow import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    ResearchArticleRunRequest,
    ResearchArticleRunResponse,
    research_article_state_to_run_response,
)


async def _invoke_research_article(
    request: ResearchArticleRunRequest,
) -> ResearchArticleRunResponse:
    graph = get_research_article_graph()
    state = initial_research_article_state(
        request.query,
        max_web_results=request.max_web_results,
        max_video_results=request.max_video_results,
    )
    result = await ainvoke_with_workflow_timeout(graph, state)
    return research_article_state_to_run_response(result)


async def _invoke_content_generation(
    request: ContentGenerationRunRequest,
) -> ContentGenerationRunResponse:
    from mcp_server.interface.custom_tools_authoring import _require_graph_search

    graph_search = None
    if request.tenant_id and request.course_slug:
        graph_search = _require_graph_search()
    return await invoke_content_generation(request, graph_search=graph_search)


@mcp.tool
async def research_article(
    query: str,
    max_web_results: int = 5,
    max_video_results: int = 3,
) -> ResearchArticleRunResponse:
    """Plan research, gather web and video context, and write a journalistic article."""
    request = ResearchArticleRunRequest(
        query=query,
        max_web_results=max_web_results,
        max_video_results=max_video_results,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "research_article",
        args,
        lambda: _invoke_research_article(request),
    )


@mcp.tool
async def content_generation(
    topic: str,
    grade_level: str = "6th grade",
    tenant_id: str | None = None,
    course_slug: str | None = None,
    module_id: str | None = None,
    lesson_slug: str | None = None,
    graph_node_id: str | None = None,
    graph_query: str | None = None,
) -> ContentGenerationRunResponse:
    """Generate lesson, quiz, and PBL. Pass tenant_id+course_slug for graph-scoped output."""
    request = ContentGenerationRunRequest(
        topic=topic,
        grade_level=grade_level,
        tenant_id=tenant_id,
        course_slug=course_slug,
        module_id=module_id,
        lesson_slug=lesson_slug,
        graph_node_id=graph_node_id,
        graph_query=graph_query,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "content_generation",
        args,
        lambda: _invoke_content_generation(request),
    )
