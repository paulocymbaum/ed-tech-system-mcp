"""Async research tools and LangGraph nodes for journalistic article generation."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from mcp_server.application.agents.research_article.prompts import (
    article_system_prompt,
    article_user_prompt,
    orchestrator_system_prompt,
    orchestrator_user_prompt,
)
from mcp_server.application.agents.research_article.state import (
    ResearchArticleState,
    ToolCallRecord,
)
from mcp_server.application.integration_runtime import get_search_client, get_video_client
from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.workflow_llm_trace import record_llm_invocation
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity
from mcp_server.domain.schemas import VideoResult


def _require_chat_model() -> BaseChatModel:
    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")
    return model


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


async def _invoke_text_llm(
    *,
    system_prompt: str,
    user_prompt: str,
    llm_complexity: LLMComplexity,
) -> str:
    model = _require_chat_model()
    result = await model.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        llm_complexity=int(llm_complexity),
    )
    raw_text = _message_content(result.content)
    record_llm_invocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_output=raw_text,
        model_name=resolve_invoked_model_name(model),
        llm_complexity=int(llm_complexity),
    )
    return raw_text


async def _call_search_tavily(query: str, max_results: int) -> tuple[list[str], ToolCallRecord]:
    client = get_search_client()
    if client is None:
        raise ResourceNotFoundError("Search client has not been initialized")
    try:
        results = await client.search(query, max_results=max_results)
    except Exception as exc:
        return [], ToolCallRecord(
            tool="search_tavily",
            status="failed",
            result_count=0,
            error=str(exc),
        )
    return results, ToolCallRecord(
        tool="search_tavily",
        status="ok",
        result_count=len(results),
    )


async def _call_search_youtube(
    query: str,
    max_results: int,
) -> tuple[list[VideoResult], ToolCallRecord]:
    client = get_video_client()
    if client is None:
        raise ResourceNotFoundError("Video search client has not been initialized")
    try:
        videos = await client.search_videos(query, max_results=max_results)
    except Exception as exc:
        return [], ToolCallRecord(
            tool="search_youtube",
            status="failed",
            result_count=0,
            error=str(exc),
        )
    return videos, ToolCallRecord(
        tool="search_youtube",
        status="ok",
        result_count=len(videos),
    )


async def agent_plan_research(state: ResearchArticleState) -> dict[str, object]:
    """Agent node: produce an editorial brief before tool orchestration."""
    brief = await _invoke_text_llm(
        system_prompt=orchestrator_system_prompt(),
        user_prompt=orchestrator_user_prompt(state["query"]),
        llm_complexity=LLMComplexity.MEDIUM,
    )
    return {"research_brief": brief.strip()}


def dispatch_parallel_tools(state: ResearchArticleState) -> list[Send]:
    """Fan out to async Tavily and YouTube tool nodes after planning."""
    return [
        Send("tool_search_tavily", state),
        Send("tool_search_youtube", state),
    ]


async def tool_search_tavily(state: ResearchArticleState) -> dict[str, object]:
    """Async tool node: Tavily web search."""
    web_results, record = await _call_search_tavily(state["query"], state["max_web_results"])
    return {
        "web_results": web_results,
        "tavily_tool_call": record,
    }


async def tool_search_youtube(state: ResearchArticleState) -> dict[str, object]:
    """Async tool node: YouTube video search."""
    videos, record = await _call_search_youtube(state["query"], state["max_video_results"])
    return {
        "videos": videos,
        "youtube_tool_call": record,
    }


async def merge_context(state: ResearchArticleState) -> dict[str, object]:
    """Merge web and video tool outputs into one narrative context block."""
    tool_calls: list[ToolCallRecord] = []
    if tavily_record := state.get("tavily_tool_call"):
        tool_calls.append(tavily_record)
    if youtube_record := state.get("youtube_tool_call"):
        tool_calls.append(youtube_record)

    merged_context = _format_merged_context(
        query=state["query"],
        research_brief=state.get("research_brief", ""),
        web_results=state.get("web_results", []),
        videos=state.get("videos", []),
    )
    return {
        "merged_context": merged_context,
        "tool_calls": tool_calls,
    }


def _format_merged_context(
    *,
    query: str,
    research_brief: str,
    web_results: list[str],
    videos: list[VideoResult],
) -> str:
    web_section = "\n".join(f"- {snippet}" for snippet in web_results) or "- (no web results)"
    video_lines = [f"- {video.title} ({video.channel}) — {video.url}" for video in videos]
    video_section = "\n".join(video_lines) or "- (no video results)"
    return (
        f"Query: {query}\n\n"
        f"Editorial brief:\n{research_brief}\n\n"
        f"Web sources (Tavily):\n{web_section}\n\n"
        f"Video sources (YouTube):\n{video_section}"
    )


async def write_article(state: ResearchArticleState) -> dict[str, object]:
    """Generate journalistic article text from merged research context."""
    article = await _invoke_text_llm(
        system_prompt=article_system_prompt(),
        user_prompt=article_user_prompt(
            query=state["query"],
            research_brief=state.get("research_brief", ""),
            merged_context=state.get("merged_context", ""),
        ),
        llm_complexity=LLMComplexity.HIGH,
    )
    return {
        "article": article.strip(),
        "generation_complete": True,
    }
