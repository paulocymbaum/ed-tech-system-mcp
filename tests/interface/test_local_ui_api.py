"""Tests for the local workflow UI API."""

import json
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    set_workflow_execution_config,
)
from mcp_server.application.workflow_runtime import (
    reset_document_video_workflow,
    set_document_video_workflow,
)
from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.interface.local_ui.api import create_local_ui_app


class _UiContentModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "ui-content-stub"

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


class _FakeRepository:
    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        return [DocumentHit(id="1", title=query, content="lesson body")]


class _FakeVideoClient:
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        return [VideoResult(title="Video", channel="Ch", url="https://example.com")]


def test_list_workflows_returns_langgraph_metadata() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows")

    assert response.status_code == 200
    workflows = response.json()
    assert len(workflows) >= 1
    workflow = workflows[0]
    assert workflow["framework"] == "langgraph"
    assert any(node["kind"] == "start" for node in workflow["nodes"])
    assert any(edge["source"] == "__start__" for edge in workflow["edges"])


def test_get_unknown_workflow_returns_404() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/does-not-exist")

    assert response.status_code == 404


def test_post_run_content_generation_returns_response_when_wired() -> None:
    set_chat_model(_UiContentModel())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/content-generation/run",
        json={"topic": "fractions", "grade_level": "6th grade"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "fractions"
    assert body["generation_complete"] is True
    assert body["lesson"]["topic"] == "fractions"
    assert len(body["quiz"]["questions"]) >= 3
    reset_chat_model()


def test_post_run_workflow_returns_response_when_wired() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=5.0,
        )
    )
    set_document_video_workflow(DocumentVideoWorkflow(_FakeRepository(), _FakeVideoClient()))
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/document-video-discovery/run",
        json={"query": "algebra", "document_limit": 5, "video_limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "algebra"
    assert body["document_count"] == 1
    assert body["video_count"] == 1
    reset_document_video_workflow()


def test_post_run_workflow_returns_503_when_uninitialized() -> None:
    reset_document_video_workflow()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/document-video-discovery/run",
        json={"query": "algebra"},
    )

    assert response.status_code == 503
    assert "not been initialized" in response.json()["detail"]


def test_local_ui_lifespan_bootstraps_application_runtime() -> None:
    """Uvicorn reload workers import app directly; lifespan must wire the runtime."""
    with (
        patch("mcp_server.interface.local_ui.api.bootstrap_environment") as mock_env,
        patch("mcp_server.interface.local_ui.api.bootstrap_application_runtime") as mock_runtime,
        TestClient(create_local_ui_app(bootstrap_runtime=True)) as client,
    ):
        response = client.get("/api/health")

    assert response.status_code == 200
    mock_env.assert_called_once()
    mock_runtime.assert_called_once()
