"""MCP tools for Groq-backed LangGraph workflows (research article, content generation)."""

from __future__ import annotations

from mcp_server.application.agent import workflow_timeout_seconds
from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.agents.research_article.graph import (
    get_research_article_graph,
    initial_research_article_state,
)
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation_workflow import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    ResearchArticleRunRequest,
    ResearchArticleRunResponse,
    content_generation_state_to_run_response,
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
    result, trace = await invoke_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    )
    return research_article_state_to_run_response(result, trace=trace)


async def _invoke_content_generation(
    request: ContentGenerationRunRequest,
) -> ContentGenerationRunResponse:
    graph = get_content_generation_graph()
    state = initial_content_generation_state(
        request.topic,
        grade_level=request.grade_level,
    )
    result, trace = await invoke_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    )
    return content_generation_state_to_run_response(result, trace=trace)


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
) -> ContentGenerationRunResponse:
    """Generate a structured lesson, quiz, and problem-based learning project."""
    request = ContentGenerationRunRequest(
        topic=topic,
        grade_level=grade_level,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "content_generation",
        args,
        lambda: _invoke_content_generation(request),
    )
