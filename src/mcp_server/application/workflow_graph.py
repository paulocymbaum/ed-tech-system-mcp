"""LangGraph workflow introspection for local visualization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field


class GraphNodeView(BaseModel):
    """Renderable workflow node."""

    id: str
    label: str
    kind: str = Field(description="start | end | node")


class GraphEdgeView(BaseModel):
    """Directed edge between workflow nodes."""

    source: str
    target: str


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


def workflow_graph_view(workflow: RegisteredWorkflow) -> WorkflowGraphView:
    """Convert a compiled LangGraph into a UI-friendly graph view."""
    drawable = workflow.graph.get_graph()
    nodes = [
        GraphNodeView(id=node_id, label=_node_label(node_id), kind=_node_kind(node_id))
        for node_id in drawable.nodes
    ]
    edges = [GraphEdgeView(source=edge.source, target=edge.target) for edge in drawable.edges]
    return WorkflowGraphView(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        nodes=nodes,
        edges=edges,
    )
