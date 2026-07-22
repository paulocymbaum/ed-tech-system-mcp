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


def test_tavily_search_graph_layout_places_end_after_search() -> None:
    reset_registered_workflows_cache()
    workflow = next(item for item in list_registered_workflows() if item.id == "tavily-search")
    view = workflow_graph_view(workflow)
    positions = {node.id: node.x for node in view.nodes}

    assert positions["__start__"] < positions["search_web"]
    assert positions["search_web"] < positions["__end__"]
    reset_registered_workflows_cache()


def test_youtube_search_graph_layout_places_end_after_search() -> None:
    reset_registered_workflows_cache()
    workflow = next(item for item in list_registered_workflows() if item.id == "youtube-search")
    view = workflow_graph_view(workflow)
    positions = {node.id: node.x for node in view.nodes}

    assert positions["__start__"] < positions["search_videos"]
    assert positions["search_videos"] < positions["__end__"]
    reset_registered_workflows_cache()


def test_research_article_graph_layout_orders_agent_tool_merge_write_nodes() -> None:
    reset_registered_workflows_cache()
    workflow = next(item for item in list_registered_workflows() if item.id == "research-article")
    view = workflow_graph_view(workflow)
    positions = {node.id: node.x for node in view.nodes}
    async_edges = {(edge.source, edge.target) for edge in view.edges if edge.kind == "async"}

    assert positions["__start__"] < positions["agent_plan_research"]
    assert positions["agent_plan_research"] < positions["merge_context"]
    assert positions["merge_context"] < positions["write_article"]
    assert positions["write_article"] < positions["__end__"]
    assert positions["tool_search_tavily"] == positions["tool_search_youtube"]
    assert positions["tool_search_tavily"] < positions["merge_context"]
    assert ("agent_plan_research", "tool_search_tavily") in async_edges
    assert ("agent_plan_research", "tool_search_youtube") in async_edges
    reset_registered_workflows_cache()
