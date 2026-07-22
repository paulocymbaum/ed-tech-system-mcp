"""Application agent and workflow registration tests."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_server.application.agent import (
    list_registered_workflows,
    reset_registered_workflows_cache,
    workflow_timeout_seconds,
)
from mcp_server.application.integration_runtime import reset_integration_clients
from mcp_server.application.workflow_config import reset_workflow_execution_config


def test_list_registered_workflows_memoizes_registered_list() -> None:
    reset_registered_workflows_cache()
    first = list_registered_workflows()
    second = list_registered_workflows()

    assert first is second
    reset_registered_workflows_cache()


def test_reset_registered_workflows_cache_rebuilds_on_next_call() -> None:
    reset_registered_workflows_cache()
    first = list_registered_workflows()
    reset_registered_workflows_cache()
    second = list_registered_workflows()

    assert first is not second
    reset_registered_workflows_cache()


async def test_compiled_graph_shared_by_run_and_registry(monkeypatch) -> None:
    reset_registered_workflows_cache()
    from mcp_server.application.agents.tavily_search.graph import (
        build_tavily_search_graph,
        reset_tavily_search_graph_cache,
    )
    from mcp_server.application.integration_runtime import set_search_client
    from mcp_server.domain.interfaces import ISearchClient

    reset_tavily_search_graph_cache()
    build_count = 0
    original_build = build_tavily_search_graph

    def counting_build():
        nonlocal build_count
        build_count += 1
        return original_build()

    monkeypatch.setattr(
        "mcp_server.application.agents.tavily_search.graph.build_tavily_search_graph",
        counting_build,
    )

    from mcp_server.application.workflow_config import (
        WorkflowExecutionConfig,
        set_workflow_execution_config,
    )

    class _SearchClient(ISearchClient):
        async def search(self, query: str, max_results: int = 5) -> list[str]:
            return [f"{query}:{max_results}"]

    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=5.0,
        )
    )
    set_search_client(_SearchClient())

    workflows = list_registered_workflows()
    tavily = next(workflow for workflow in workflows if workflow.id == "tavily-search")
    from mcp_server.application.agents.tavily_search.graph import (
        get_tavily_search_graph,
        initial_tavily_search_state,
    )

    graph = get_tavily_search_graph()
    await graph.ainvoke(initial_tavily_search_state("algebra", max_results=2))

    assert build_count == 1
    assert tavily.graph is graph
    reset_registered_workflows_cache()
    reset_integration_clients()


def test_list_registered_workflows_returns_search_workflow_metadata() -> None:
    reset_registered_workflows_cache()
    workflows = list_registered_workflows()

    assert len(workflows) >= 3
    workflow_ids = {workflow.id for workflow in workflows}
    assert "tavily-search" in workflow_ids
    assert "youtube-search" in workflow_ids
    tavily = next(workflow for workflow in workflows if workflow.id == "tavily-search")
    youtube = next(workflow for workflow in workflows if workflow.id == "youtube-search")
    assert tavily.name == "Tavily Web Search"
    assert youtube.name == "YouTube Video Search"
    reset_registered_workflows_cache()


def test_workflow_timeout_seconds_falls_back_to_config_json_defaults() -> None:
    reset_workflow_execution_config()
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    assert workflow_timeout_seconds() == raw["workflow_timeout"]
    reset_workflow_execution_config()
