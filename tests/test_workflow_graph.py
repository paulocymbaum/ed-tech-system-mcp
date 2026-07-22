"""Tests for workflow graph layout and edge classification."""

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.workflow_graph import workflow_graph_view


def test_content_generation_graph_layout_places_end_node_after_merge() -> None:
    reset_registered_workflows_cache()
    workflow = next(item for item in list_registered_workflows() if item.id == "content-generation")
    view = workflow_graph_view(workflow)
    positions = {node.id: node.x for node in view.nodes}

    assert positions["__start__"] < positions["generate_lesson"]
    assert positions["validate_pbl"] < positions["merge_results"]
    assert positions["merge_results"] < positions["__end__"]

    lesson = next(node for node in view.nodes if node.id == "generate_lesson")
    validate = next(node for node in view.nodes if node.id == "validate_lesson")
    assert lesson.y < validate.y
    assert lesson.x < validate.x

    retry_edges = [edge for edge in view.edges if edge.kind == "retry"]
    failure_edges = [edge for edge in view.edges if edge.kind == "failure"]
    forward_edges = [edge for edge in view.edges if edge.kind == "forward"]
    assert ("validate_lesson", "generate_lesson") in {
        (edge.source, edge.target) for edge in retry_edges
    }
    assert ("validate_lesson", "merge_results") in {
        (edge.source, edge.target) for edge in failure_edges
    }
    assert ("validate_pbl", "merge_results") in {
        (edge.source, edge.target) for edge in forward_edges
    }
    reset_registered_workflows_cache()
