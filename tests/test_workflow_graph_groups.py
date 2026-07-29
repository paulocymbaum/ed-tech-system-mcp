"""Tests for workflow graph introspection and node groups."""

from __future__ import annotations

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.workflow_graph import workflow_graph_view


def test_rag_workflows_expose_collapsible_node_groups() -> None:
    reset_registered_workflows_cache()
    workflows = {workflow.id: workflow for workflow in list_registered_workflows()}

    for workflow_id in ("rag-retrieval", "rag-validation"):
        view = workflow_graph_view(workflows[workflow_id])
        assert view.node_groups, f"{workflow_id} should define node_groups"
        rag_group = next(group for group in view.node_groups if group.id == "rag_pipeline")
        assert rag_group.label == "RAG Pipeline"
        assert rag_group.default_collapsed is True
        assert "embed_query" in rag_group.node_ids
        assert "merge_context" in rag_group.node_ids


def test_rag_validation_graph_includes_document_and_validate_nodes() -> None:
    reset_registered_workflows_cache()
    workflows = {workflow.id: workflow for workflow in list_registered_workflows()}
    view = workflow_graph_view(workflows["rag-validation"])
    node_ids = {node.id for node in view.nodes}
    assert "load_document" in node_ids
    assert "index_document" in node_ids
    assert "validate_retrieval" in node_ids
    group_ids = {group.id for group in view.node_groups}
    assert "document_pipeline" in group_ids
    assert "rag_pipeline" in group_ids
