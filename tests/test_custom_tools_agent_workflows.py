"""MCP tool contract tests for Groq-backed agent workflows."""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.integration_runtime import (
    reset_integration_clients,
    set_search_client,
    set_video_client,
)
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.token_counting_runtime import reset_token_counter, set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import VideoResult
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter
from mcp_server.interface.custom_tools_agent_workflows import (
    content_generation,
    research_article,
)


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
                "Researchers are finding new roles for frogs in ecology and education."
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


class _ContentGenerationModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "content-generation-stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = "\n".join(str(message.content) for message in messages).lower()
        if "quiz" in text and "assessment" in text:
            payload = {
                "title": "Quiz: fractions",
                "questions": [
                    {
                        "question": "Q1",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                    {
                        "question": "Q2",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                    {
                        "question": "Q3",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                ],
            }
        elif "problem-based learning" in text:
            payload = {
                "title": "PBL: fractions",
                "driving_question": "How can we apply fractions?",
                "scenario": "A community project needs help dividing resources fairly.",
                "learning_objectives": ["Apply fractions"],
                "deliverables": [
                    {"name": "Plan", "description": "A written project plan with milestones."}
                ],
                "duration_days": 5,
            }
        else:
            payload = {
                "title": "Lesson: fractions",
                "topic": "fractions",
                "grade_level": "6th grade",
                "objectives": ["Understand fractions"],
                "sections": [
                    {"heading": "Intro", "content": "Fractions represent parts of a whole."},
                    {"heading": "Practice", "content": "Students solve guided fraction problems."},
                ],
                "summary": "Students understand fractions as parts of a whole.",
            }
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=json.dumps(payload)))]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture(autouse=True)
def _reset_agent_workflow_runtime() -> None:
    reset_integration_clients()
    reset_chat_model()
    reset_token_counter()
    reset_workflow_execution_config()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    yield
    reset_integration_clients()
    reset_chat_model()
    reset_token_counter()
    reset_workflow_execution_config()


async def test_research_article_mcp_tool_returns_article() -> None:
    set_chat_model(_ResearchArticleModel())
    set_search_client(_FakeSearchClient())
    set_video_client(_FakeVideoClient())

    response = await research_article("frogs in science", max_web_results=2, max_video_results=1)

    assert response.query == "frogs in science"
    assert response.generation_complete is True
    assert "Frogs in Modern Science" in response.article
    assert response.web_result_count == 2
    assert response.video_count == 1
    assert response.trace == []


async def test_content_generation_mcp_tool_returns_lesson_quiz_and_pbl() -> None:
    set_chat_model(_ContentGenerationModel())
    set_token_counter(TiktokenTokenCounter())

    response = await content_generation("fractions", grade_level="6th grade")

    assert response.topic == "fractions"
    assert response.grade_level == "6th grade"
    assert response.generation_complete is True
    assert response.lesson is not None
    assert response.lesson.topic == "fractions"
    assert response.quiz is not None
    assert len(response.quiz.questions) >= 3
    assert response.pbl is not None
    assert response.trace == []
