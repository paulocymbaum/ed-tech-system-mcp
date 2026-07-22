"""Application agent and workflow registration tests."""

from __future__ import annotations

import json
from pathlib import Path

import mcp_server.application.agent as agent_module
from mcp_server.application.agent import (
    list_registered_workflows,
    reset_compiled_graph_cache,
    reset_registered_workflows_cache,
    run_document_video_graph,
    workflow_timeout_seconds,
)
from mcp_server.application.workflow_config import reset_workflow_execution_config


def test_list_registered_workflows_memoizes_compiled_graph(monkeypatch) -> None:
    reset_registered_workflows_cache()
    build_count = 0
    original_build = agent_module.build_document_video_graph

    def counting_build():
        nonlocal build_count
        build_count += 1
        return original_build()

    monkeypatch.setattr(agent_module, "build_document_video_graph", counting_build)

    first = list_registered_workflows()
    second = list_registered_workflows()

    assert build_count == 1
    assert first is second
    reset_registered_workflows_cache()


def test_reset_registered_workflows_cache_rebuilds_on_next_call(monkeypatch) -> None:
    reset_registered_workflows_cache()
    build_count = 0
    original_build = agent_module.build_document_video_graph

    def counting_build():
        nonlocal build_count
        build_count += 1
        return original_build()

    monkeypatch.setattr(agent_module, "build_document_video_graph", counting_build)

    first = list_registered_workflows()
    reset_registered_workflows_cache()
    second = list_registered_workflows()

    assert build_count == 2
    assert first is not second
    reset_registered_workflows_cache()


async def test_compiled_graph_shared_by_run_and_registry(monkeypatch) -> None:
    reset_registered_workflows_cache()
    reset_compiled_graph_cache()
    build_count = 0
    original_build = agent_module.build_document_video_graph

    def counting_build():
        nonlocal build_count
        build_count += 1
        return original_build()

    monkeypatch.setattr(agent_module, "build_document_video_graph", counting_build)

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

    class _Repo:
        async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
            return [DocumentHit(id="1", title=query, content="body")]

    class _Video:
        async def search_videos(
            self,
            query: str,
            max_results: int = 5,
            language: str = "en",
            safe_search: bool = True,
        ) -> list[VideoResult]:
            return [VideoResult(title="V", channel="C", url="https://example.com")]

    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=5.0,
        )
    )
    set_document_video_workflow(DocumentVideoWorkflow(_Repo(), _Video()))

    workflows = list_registered_workflows()
    await run_document_video_graph("algebra")

    assert build_count == 1
    assert workflows[0].graph is agent_module._get_compiled_graph()
    reset_registered_workflows_cache()
    reset_document_video_workflow()


def test_list_registered_workflows_returns_document_video_discovery_metadata() -> None:
    reset_registered_workflows_cache()
    workflows = list_registered_workflows()

    assert len(workflows) == 1
    workflow = workflows[0]
    assert workflow.id == "document-video-discovery"
    assert workflow.name == "Document + Video Discovery"
    assert "educational documents" in workflow.description.lower()
    reset_registered_workflows_cache()


def test_workflow_timeout_seconds_falls_back_to_config_json_defaults() -> None:
    reset_workflow_execution_config()
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    assert workflow_timeout_seconds() == raw["workflow_timeout"]
    reset_workflow_execution_config()
