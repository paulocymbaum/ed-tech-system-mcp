"""Structure-only course graph proposal (GAP-SC-002). No lesson bodies."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_server.domain.exceptions import DomainValidationError

ScaffoldKind = Literal["root", "module", "lesson", "section"]

ALLOWED_KINDS: frozenset[str] = frozenset({"root", "module", "lesson", "section"})
FORBIDDEN_BODY_KEYS: frozenset[str] = frozenset(
    {
        "readme",
        "markdown",
        "quiz",
        "project",
        "questions",
        "tests",
        "body",
        "content",
        "harness_lesson",
        "harness_quiz",
        "harness_project",
        "objectives",
        "starter",
        "testboilerplate",
        "test_boilerplate",
    }
)


class ScaffoldNode(BaseModel):
    """One import_graph / apply_scaffold_graph node."""

    model_config = ConfigDict(extra="forbid")

    legacy_node_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: ScaffoldKind
    graph_index: str = Field(min_length=1)

    @field_validator("legacy_node_id", "label", "graph_index")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "field must be non-empty"
            raise ValueError(msg)
        return stripped


class ScaffoldEdge(BaseModel):
    """Parent/child edge using legacy node ids."""

    model_config = ConfigDict(extra="forbid")

    parent_legacy_id: str = Field(min_length=1)
    child_legacy_id: str = Field(min_length=1)
    position: int = 0

    @field_validator("parent_legacy_id", "child_legacy_id")
    @classmethod
    def _strip_ids(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "legacy id must be non-empty"
            raise ValueError(msg)
        return stripped


class ScaffoldProposal(BaseModel):
    """Structure-only proposal DTO (BFF extractScaffoldProposal root)."""

    model_config = ConfigDict(extra="ignore")

    nodes: list[ScaffoldNode] = Field(min_length=1)
    edges: list[ScaffoldEdge] = Field(default_factory=list)


def slugify_course_title(title: str) -> str:
    """Derive a course slug from a title (BFF-compatible)."""
    chars: list[str] = []
    previous_dash = False
    for raw in title.strip().lower():
        if raw.isalnum():
            chars.append(raw)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    slug = "".join(chars).strip("-") or "course"
    return slug[:80]


def raw_forbidden_body_keys(payload: Any) -> list[str]:
    """Return forbidden body keys found on nodes or the proposal object."""
    found: list[str] = []
    if not isinstance(payload, dict):
        return found
    for key in payload:
        if str(key).lower() in FORBIDDEN_BODY_KEYS:
            found.append(str(key))
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for key in node:
                if str(key).lower() in FORBIDDEN_BODY_KEYS:
                    found.append(str(key))
    return found


def validate_scaffold_proposal(proposal: ScaffoldProposal) -> list[str]:
    """Return invariant findings; empty list means the graph is usable."""
    findings: list[str] = []
    ids = [node.legacy_node_id for node in proposal.nodes]
    if len(ids) != len(set(ids)):
        findings.append("legacy_node_id values must be unique")

    indexes = [node.graph_index for node in proposal.nodes]
    if len(indexes) != len(set(indexes)):
        findings.append("graph_index values must be unique")

    kinds = {node.legacy_node_id: node.kind for node in proposal.nodes}
    id_set = set(ids)
    roots = [node for node in proposal.nodes if node.kind == "root"]
    if len(roots) != 1:
        findings.append("proposal must contain exactly one root node")

    children: set[str] = set()
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in proposal.edges:
        if edge.parent_legacy_id not in id_set or edge.child_legacy_id not in id_set:
            findings.append("edges must reference existing legacy_node_id values")
            continue
        if edge.parent_legacy_id == edge.child_legacy_id:
            findings.append("edges must not be self-loops")
            continue
        if edge.child_legacy_id in children:
            findings.append("each child may have only one parent")
            continue
        children.add(edge.child_legacy_id)
        adjacency[edge.parent_legacy_id].append(edge.child_legacy_id)

    if roots:
        root_id = roots[0].legacy_node_id
        seen: set[str] = set()
        stack = [root_id]
        while stack:
            current = stack.pop()
            if current in seen:
                findings.append("proposal graph must be acyclic")
                break
            seen.add(current)
            stack.extend(adjacency.get(current, []))
        if findings and findings[-1] == "proposal graph must be acyclic":
            return findings
        if seen != id_set:
            findings.append("all nodes must be connected from the root")
        if kinds.get(root_id) != "root":
            findings.append("root node kind must be root")

    return findings


def require_valid_scaffold_proposal(proposal: ScaffoldProposal) -> ScaffoldProposal:
    """Raise when structure invariants fail."""
    findings = validate_scaffold_proposal(proposal)
    if findings:
        raise DomainValidationError("; ".join(findings))
    return proposal
