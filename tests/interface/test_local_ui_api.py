"""Tests for the local workflow UI API."""

from unittest.mock import patch

from fastapi.testclient import TestClient

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
from mcp_server.interface.local_ui.api import create_local_ui_app


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
