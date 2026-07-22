"""Tests for the local workflow UI API."""

import json
import os
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.integration_runtime import reset_integration_clients
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.retrieval_runtime import (
    reset_retrieval_clients,
    set_chunking_strategy,
    set_embedding_provider,
    set_reranker,
    set_vector_index_writer,
    set_vector_retriever,
)
from mcp_server.application.token_counting_runtime import set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.infrastructure.rerank.noop_reranker import NoOpReranker
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter
from mcp_server.interface.local_ui.api import create_local_ui_app
from mcp_server.main import bootstrap_application_runtime, bootstrap_environment
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import load_settings
from rag_fakes import (
    FakeChunkingStrategy,
    FakeEmbeddingProvider,
    FixtureAwareRetriever,
    RecordingIndexWriter,
)


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


def _bootstrap_live_runtime() -> None:
    bootstrap_environment()
    bootstrap_application_runtime(load_operational_config(), load_settings())


def test_list_workflows_returns_langgraph_metadata() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows")

    assert response.status_code == 200
    workflows = response.json()
    assert len(workflows) >= 2
    workflow = workflows[0]
    assert workflow["framework"] == "langgraph"
    assert any(node["kind"] == "start" for node in workflow["nodes"])
    assert any(edge["source"] == "__start__" for edge in workflow["edges"])
    workflow_ids = {item["id"] for item in workflows}
    assert "tavily-search" in workflow_ids
    assert "youtube-search" in workflow_ids


def test_get_unknown_workflow_returns_404() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/does-not-exist")

    assert response.status_code == 404


def test_post_run_content_generation_returns_response_when_wired() -> None:
    set_chat_model(_UiContentModel())
    set_token_counter(TiktokenTokenCounter())
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
    llm_steps = [step for step in body["trace"] if step.get("llm_io")]
    assert llm_steps
    assert llm_steps[0]["llm_io"]["input_tokens"] > 0
    assert llm_steps[0]["llm_io"]["total_tokens"] > 0
    reset_chat_model()


@pytest.mark.skipif(
    not os.getenv("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY not set",
)
def test_post_run_tavily_search_returns_live_results() -> None:
    reset_integration_clients()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    _bootstrap_live_runtime()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/tavily-search/run",
        json={"query": "education", "max_results": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "education"
    assert body["result_count"] >= 1
    assert len(body["results"]) >= 1
    assert len(body["trace"]) >= 1
    assert body["trace"][0]["node_id"] == "search_web"
    reset_integration_clients()


@pytest.mark.skipif(
    not os.getenv("YOUTUBE_API_KEY"),
    reason="YOUTUBE_API_KEY not set",
)
def test_post_run_youtube_search_returns_live_results() -> None:
    reset_integration_clients()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    _bootstrap_live_runtime()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/youtube-search/run",
        json={"query": "education", "max_results": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "education"
    assert body["video_count"] >= 1
    assert len(body["videos"]) >= 1
    assert body["videos"][0]["url"].startswith("https://www.youtube.com/watch?v=")
    assert len(body["trace"]) >= 1
    assert body["trace"][0]["node_id"] == "search_videos"
    reset_integration_clients()


def test_post_run_tavily_search_returns_503_when_uninitialized() -> None:
    reset_integration_clients()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/tavily-search/run",
        json={"query": "algebra"},
    )

    assert response.status_code == 503
    assert "not been initialized" in response.json()["detail"]


def test_post_run_youtube_search_returns_503_when_uninitialized() -> None:
    reset_integration_clients()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/youtube-search/run",
        json={"query": "algebra"},
    )

    assert response.status_code == 503
    assert "not been initialized" in response.json()["detail"]


def test_post_run_rag_validation_returns_response_when_wired() -> None:
    set_token_counter(TiktokenTokenCounter())
    writer = RecordingIndexWriter()
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(FixtureAwareRetriever(writer))
    set_reranker(NoOpReranker())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/rag-validation/run",
        json={
            "query": "How does photosynthesis convert light energy?",
            "document_title": "Custom corpus",
            "document_text": (
                "# Custom\n\nPhotosynthesis uses chlorophyll during light-dependent reactions to make glucose."
            ),
            "expected_phrases": ["chlorophyll", "light-dependent reactions", "glucose"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["index_complete"] is True
    assert body["validation_passed"] is True
    assert body["document_title"] == "Custom corpus"
    assert body["document_source"] == "inline"
    assert body["chunk_count"] >= 1
    assert body["rag_benchmarks"]["phrase_coverage"] == 1.0
    assert body["rag_benchmarks"]["any_phrase_hit"] == 1.0
    assert body["rag_evaluation_context"]["score_kind"] in {"cosine", "rrf", "reranker"}
    assert body["matched_phrases"] == ["chlorophyll", "light-dependent reactions", "glucose"]
    assert body["missing_phrases"] == []
    assert len(body["trace"]) >= 6
    validate_steps = [step for step in body["trace"] if step["node_id"] == "validate_retrieval"]
    assert validate_steps
    assert validate_steps[0]["output_update"]["rag_benchmarks"]["phrase_coverage"] == 1.0
    assert "rag_evaluation_context" in validate_steps[0]["output_update"]
    merge_steps = [step for step in body["trace"] if step["node_id"] == "merge_context"]
    assert merge_steps
    assert "retrieval_metrics" in merge_steps[0]["output_update"]
    assert "rag_evaluation_context" in merge_steps[0]["output_update"]
    node_ids = {step["node_id"] for step in body["trace"]}
    assert "load_document" in node_ids
    assert "index_document" in node_ids
    assert "embed_query" in node_ids
    assert "validate_retrieval" in node_ids
    reset_retrieval_clients()
    reset_workflow_execution_config()


def test_list_workflows_includes_rag_validation_node_groups() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/rag-validation")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "rag-validation"
    group_ids = {group["id"] for group in body["node_groups"]}
    assert "rag_pipeline" in group_ids
    assert "document_pipeline" in group_ids


def test_get_rag_validation_document_defaults() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/rag-validation/document-defaults")

    assert response.status_code == 200
    body = response.json()
    assert "chlorophyll" in body["document_text"]
    assert body["expected_phrases"]


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
