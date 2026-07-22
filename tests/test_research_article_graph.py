"""Tests for the research-article LangGraph workflow."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.agents.research_article.graph import (
    build_research_article_graph,
    reset_research_article_graph_cache,
    run_research_article_graph,
)
from mcp_server.application.integration_runtime import (
    reset_integration_clients,
    set_search_client,
    set_video_client,
)
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import VideoResult


class _FakeSearchClient(ISearchClient):
    async def search(self, query: str, max_results: int = 5) -> list[str]:
        return [f"Web insight about {query} ({index})" for index in range(max_results)]


class _FakeVideoClient(IVideoSearchClient):
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        return [
            VideoResult(
                title=f"Video on {query}",
                channel="Edu Channel",
                url="https://www.youtube.com/watch?v=test123",
            )
        ]


class _ResearchArticleModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "research-article-stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = "\n".join(str(message.content) for message in messages).lower()
        if "journalistic article" in text or "write the journalistic article" in text:
            content = (
                "# Frogs in Modern Science\n\n"
                "Researchers are finding new roles for frogs in ecology and education.\n\n"
                "Web reports highlight amphibian biodiversity trends.\n\n"
                "Educational videos help classrooms explore species adaptation."
            )
        else:
            content = (
                "Research angle: explain why frogs matter in ecology and education. "
                "Gather web reporting on biodiversity and classroom videos on adaptation."
            )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_chat_model()
    reset_integration_clients()
    reset_research_article_graph_cache()
    reset_registered_workflows_cache()
    reset_workflow_execution_config()
    yield
    reset_workflow_execution_config()


async def test_research_article_graph_runs_parallel_tools_and_writes_article() -> None:
    set_chat_model(_ResearchArticleModel())
    set_search_client(_FakeSearchClient())
    set_video_client(_FakeVideoClient())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )

    result = await run_research_article_graph(
        "frog species",
        max_web_results=2,
        max_video_results=1,
    )

    assert result["generation_complete"] is True
    assert "Frogs in Modern Science" in result["article"]
    assert len(result["web_results"]) == 2
    assert len(result["videos"]) == 1
    assert len(result["tool_calls"]) == 2
    assert {call["tool"] for call in result["tool_calls"]} == {
        "search_tavily",
        "search_youtube",
    }
    assert "Web sources (Tavily)" in result["merged_context"]
    assert "Video sources (YouTube)" in result["merged_context"]


async def test_research_article_trace_records_orchestration_and_llm_steps() -> None:
    set_chat_model(_ResearchArticleModel())
    set_search_client(_FakeSearchClient())
    set_video_client(_FakeVideoClient())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    graph = build_research_article_graph()
    from mcp_server.application.agents.research_article.graph import initial_research_article_state

    _, trace = await invoke_graph_with_trace(
        graph,
        initial_research_article_state("climate education"),
        timeout_seconds=30.0,
    )

    node_ids = [step.node_id for step in trace]
    assert node_ids == [
        "agent_plan_research",
        "tool_search_tavily",
        "tool_search_youtube",
        "merge_context",
        "write_article",
    ]
    tool_steps = [step for step in trace if step.node_id.startswith("tool_search_")]
    assert len(tool_steps) == 2
    merge = next(step for step in trace if step.node_id == "merge_context")
    assert merge.output_update.get("tool_calls")
    llm_steps = [step for step in trace if step.llm_io is not None]
    assert len(llm_steps) == 2


def test_research_article_workflow_is_registered() -> None:
    workflow_ids = {workflow.id for workflow in list_registered_workflows()}
    assert "research-article" in workflow_ids
