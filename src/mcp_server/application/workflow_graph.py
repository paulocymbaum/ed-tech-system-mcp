"""LangGraph workflow introspection for local visualization."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

_RETRY_EDGES = frozenset(
    {
        ("validate_lesson", "generate_lesson"),
        ("validate_quiz", "generate_quiz"),
        ("validate_pbl", "generate_pbl"),
    }
)

_FAILURE_EDGES = frozenset(
    {
        ("validate_lesson", "merge_results"),
        ("validate_quiz", "merge_results"),
    }
)

_GENERATION_NODES = frozenset({"generate_lesson", "generate_quiz", "generate_pbl"})
_LAYOUT_X_GAP = 220
_LAYOUT_MAIN_Y = 140
_LAYOUT_RETRY_Y = 40

_WORKFLOW_SPINES: dict[str, list[str]] = {
    "content-generation": [
        "__start__",
        "generate_lesson",
        "validate_lesson",
        "generate_quiz",
        "validate_quiz",
        "generate_pbl",
        "validate_pbl",
        "merge_results",
        "__end__",
    ],
    "document-video-discovery": [
        "__start__",
        "fetch_documents",
        "derive_search_terms",
        "search_videos",
        "merge_results",
        "__end__",
    ],
    "tavily-search": [
        "__start__",
        "search_web",
        "__end__",
    ],
    "youtube-search": [
        "__start__",
        "search_videos",
        "__end__",
    ],
}


class GraphNodeView(BaseModel):
    """Renderable workflow node."""

    id: str
    label: str
    kind: str = Field(description="start | end | node")
    x: int = 0
    y: int = 0


class GraphEdgeView(BaseModel):
    """Directed edge between workflow nodes."""

    source: str
    target: str
    kind: str = Field(default="forward", description="forward | retry | failure")


class WorkflowGraphView(BaseModel):
    """Serializable graph structure for the local workflow UI."""

    id: str
    name: str
    description: str
    framework: str = "langgraph"
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]


@dataclass(frozen=True, slots=True)
class RegisteredWorkflow:
    """Workflow metadata paired with a compiled LangGraph."""

    id: str
    name: str
    description: str
    graph: CompiledStateGraph[Any, Any, Any]


_START_NODE = "__start__"
_END_NODE = "__end__"


def _node_kind(node_id: str) -> str:
    if node_id == _START_NODE:
        return "start"
    if node_id == _END_NODE:
        return "end"
    return "node"


def _node_label(node_id: str) -> str:
    if node_id == _START_NODE:
        return "Start"
    if node_id == _END_NODE:
        return "End"
    return node_id.replace("_", " ").title()


def _edge_kind(source: str, target: str) -> str:
    if (source, target) in _RETRY_EDGES:
        return "retry"
    if (source, target) in _FAILURE_EDGES:
        return "failure"
    return "forward"


def _topological_order(node_ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    incoming = {node_id: 0 for node_id in node_ids}
    adjacency = {node_id: [] for node_id in node_ids}
    for source, target in edges:
        if source not in adjacency or target not in incoming:
            continue
        adjacency[source].append(target)
        incoming[target] += 1

    queue = deque(node_id for node_id in node_ids if incoming[node_id] == 0)
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for target in adjacency[current]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)

    return ordered if ordered else list(node_ids)


def _layout_order(node_ids: list[str], edges: list[tuple[str, str]], workflow_id: str) -> list[str]:
    spine = _WORKFLOW_SPINES.get(workflow_id)
    if spine is not None:
        ordered = [node_id for node_id in spine if node_id in node_ids]
        for node_id in node_ids:
            if node_id not in ordered:
                ordered.append(node_id)
        return ordered

    forward_edges = [
        (source, target)
        for source, target in edges
        if _edge_kind(source, target) == "forward"
    ]
    return _topological_order(node_ids, forward_edges)


def _layout_positions(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    *,
    workflow_id: str,
) -> dict[str, tuple[int, int]]:
    """Lay out nodes on a forward spine; generation nodes sit above for visible retry loops."""
    order = _layout_order(node_ids, edges, workflow_id)
    positions: dict[str, tuple[int, int]] = {}
    for index, node_id in enumerate(order):
        y = _LAYOUT_RETRY_Y if node_id in _GENERATION_NODES else _LAYOUT_MAIN_Y
        positions[node_id] = (index * _LAYOUT_X_GAP, y)
    for node_id in node_ids:
        positions.setdefault(node_id, (len(order) * _LAYOUT_X_GAP, _LAYOUT_MAIN_Y))
    return positions


def workflow_graph_view(workflow: RegisteredWorkflow) -> WorkflowGraphView:
    """Convert a compiled LangGraph into a UI-friendly graph view."""
    drawable = workflow.graph.get_graph()
    node_ids = list(drawable.nodes)
    edge_pairs = [(edge.source, edge.target) for edge in drawable.edges]
    positions = _layout_positions(node_ids, edge_pairs, workflow_id=workflow.id)
    nodes = [
        GraphNodeView(
            id=node_id,
            label=_node_label(node_id),
            kind=_node_kind(node_id),
            x=positions[node_id][0],
            y=positions[node_id][1],
        )
        for node_id in node_ids
    ]
    edges = [
        GraphEdgeView(
            source=edge.source,
            target=edge.target,
            kind=_edge_kind(edge.source, edge.target),
        )
        for edge in drawable.edges
    ]
    return WorkflowGraphView(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        nodes=nodes,
        edges=edges,
    )
