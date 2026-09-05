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
        ("validate", "generate"),
    }
)

_FAILURE_EDGES = frozenset(
    {
        ("validate_lesson", "merge_results"),
        ("validate_quiz", "merge_results"),
    }
)

_ASYNC_EDGES = frozenset(
    {
        ("agent_plan_research", "tool_search_tavily"),
        ("agent_plan_research", "tool_search_youtube"),
        ("tool_search_tavily", "merge_context"),
        ("tool_search_youtube", "merge_context"),
    }
)

_GENERATION_NODES = frozenset({"generate_lesson", "generate_quiz", "generate_pbl"})
_PARALLEL_TOOL_NODES = frozenset({"tool_search_tavily", "tool_search_youtube"})
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
    "research-article": [
        "__start__",
        "agent_plan_research",
        "tool_search_tavily",
        "tool_search_youtube",
        "merge_context",
        "write_article",
        "__end__",
    ],
    "project-review": [
        "__start__",
        "collect_context",
        "grade_delivery",
        "validate_grade",
        "persist_grade",
        "__end__",
    ],
    "socratic-tutor": [
        "__start__",
        "ground_context",
        "generate_reply",
        "validate_reply",
        "__end__",
    ],
    "course-scaffold": [
        "__start__",
        "generate",
        "validate",
        "__end__",
    ],
    "rag-retrieval": [
        "__start__",
        "embed_query",
        "retrieve_chunks",
        "rerank_chunks",
        "merge_context",
        "__end__",
    ],
    "rag-validation": [
        "__start__",
        "load_document",
        "index_document",
        "embed_query",
        "retrieve_chunks",
        "rerank_chunks",
        "merge_context",
        "validate_retrieval",
        "__end__",
    ],
}

_DOCUMENT_PIPELINE_NODE_IDS = (
    "load_document",
    "index_document",
)

_RAG_PIPELINE_NODE_IDS = (
    "embed_query",
    "retrieve_chunks",
    "rerank_chunks",
    "merge_context",
)

_WORKFLOW_NODE_GROUPS: dict[str, list[dict[str, object]]] = {
    "rag-retrieval": [
        {
            "id": "rag_pipeline",
            "label": "RAG Pipeline",
            "node_ids": list(_RAG_PIPELINE_NODE_IDS),
            "default_collapsed": True,
        },
    ],
    "rag-validation": [
        {
            "id": "document_pipeline",
            "label": "Document Pipeline",
            "node_ids": list(_DOCUMENT_PIPELINE_NODE_IDS),
            "default_collapsed": False,
        },
        {
            "id": "rag_pipeline",
            "label": "RAG Pipeline",
            "node_ids": list(_RAG_PIPELINE_NODE_IDS),
            "default_collapsed": True,
        },
    ],
}

_WORKFLOW_EDGES: dict[str, list[tuple[str, str]]] = {
    "research-article": [
        ("__start__", "agent_plan_research"),
        ("agent_plan_research", "tool_search_tavily"),
        ("agent_plan_research", "tool_search_youtube"),
        ("tool_search_tavily", "merge_context"),
        ("tool_search_youtube", "merge_context"),
        ("merge_context", "write_article"),
        ("write_article", "__end__"),
    ],
    "rag-retrieval": [
        ("__start__", "embed_query"),
        ("embed_query", "retrieve_chunks"),
        ("retrieve_chunks", "rerank_chunks"),
        ("retrieve_chunks", "merge_context"),
        ("rerank_chunks", "merge_context"),
        ("merge_context", "__end__"),
    ],
    "rag-validation": [
        ("__start__", "load_document"),
        ("load_document", "index_document"),
        ("index_document", "embed_query"),
        ("embed_query", "retrieve_chunks"),
        ("retrieve_chunks", "rerank_chunks"),
        ("retrieve_chunks", "merge_context"),
        ("rerank_chunks", "merge_context"),
        ("merge_context", "validate_retrieval"),
        ("validate_retrieval", "__end__"),
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
    kind: str = Field(default="forward", description="forward | retry | failure | async")


class NodeGroupView(BaseModel):
    """Collapsible group of related workflow nodes (e.g. RAG pipeline substeps)."""

    id: str
    label: str
    node_ids: list[str]
    default_collapsed: bool = True


class WorkflowGraphView(BaseModel):
    """Serializable graph structure for the local workflow UI."""

    id: str
    name: str
    description: str
    framework: str = "langgraph"
    nodes: list[GraphNodeView]
    edges: list[GraphEdgeView]
    node_groups: list[NodeGroupView] = Field(default_factory=list)


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
    if (source, target) in _ASYNC_EDGES:
        return "async"
    return "forward"


def _topological_order(node_ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    incoming = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
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
        (source, target) for source, target in edges if _edge_kind(source, target) == "forward"
    ]
    return _topological_order(node_ids, forward_edges)


def _layout_positions(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    *,
    workflow_id: str,
) -> dict[str, tuple[int, int]]:
    """Lay out nodes on a forward spine; parallel tool nodes branch above/below."""
    if workflow_id == "research-article":
        return _research_article_positions(node_ids)

    order = _layout_order(node_ids, edges, workflow_id)
    positions: dict[str, tuple[int, int]] = {}
    for index, node_id in enumerate(order):
        y = _LAYOUT_RETRY_Y if node_id in _GENERATION_NODES else _LAYOUT_MAIN_Y
        positions[node_id] = (index * _LAYOUT_X_GAP, y)
    for node_id in node_ids:
        positions.setdefault(node_id, (len(order) * _LAYOUT_X_GAP, _LAYOUT_MAIN_Y))
    return positions


def _research_article_positions(node_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Explicit layout so parallel async tool nodes are visible in the UI."""
    preset: dict[str, tuple[int, int]] = {
        "__start__": (0, _LAYOUT_MAIN_Y),
        "agent_plan_research": (_LAYOUT_X_GAP, _LAYOUT_MAIN_Y),
        "tool_search_tavily": (_LAYOUT_X_GAP * 2, _LAYOUT_RETRY_Y),
        "tool_search_youtube": (_LAYOUT_X_GAP * 2, _LAYOUT_MAIN_Y + 100),
        "merge_context": (_LAYOUT_X_GAP * 3, _LAYOUT_MAIN_Y),
        "write_article": (_LAYOUT_X_GAP * 4, _LAYOUT_MAIN_Y),
        "__end__": (_LAYOUT_X_GAP * 5, _LAYOUT_MAIN_Y),
    }
    positions: dict[str, tuple[int, int]] = {}
    for node_id in node_ids:
        positions[node_id] = preset.get(node_id, (len(preset) * _LAYOUT_X_GAP, _LAYOUT_MAIN_Y))
    return positions


def workflow_graph_view(workflow: RegisteredWorkflow) -> WorkflowGraphView:
    """Convert a compiled LangGraph into a UI-friendly graph view."""
    drawable = workflow.graph.get_graph()
    node_ids = list(drawable.nodes)
    edge_pairs = _workflow_edge_pairs(workflow.id, drawable)
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
            source=source,
            target=target,
            kind=_edge_kind(source, target),
        )
        for source, target in edge_pairs
    ]
    node_groups = [
        NodeGroupView.model_validate(group) for group in _WORKFLOW_NODE_GROUPS.get(workflow.id, [])
    ]
    return WorkflowGraphView(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        nodes=nodes,
        edges=edges,
        node_groups=node_groups,
    )


def _workflow_edge_pairs(workflow_id: str, drawable: Any) -> list[tuple[str, str]]:
    """Return drawable edges, with workflow-specific overrides for Send-based fan-out."""
    configured = _WORKFLOW_EDGES.get(workflow_id)
    if configured is not None:
        node_ids = set(drawable.nodes)
        return [
            (source, target)
            for source, target in configured
            if source in node_ids and target in node_ids
        ]
    return [(edge.source, edge.target) for edge in drawable.edges]
