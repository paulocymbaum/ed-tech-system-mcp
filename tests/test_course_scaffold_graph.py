"""Tests for structure-only course scaffold generation."""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ValidationError

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.agents.course_scaffold.graph import (
    build_course_scaffold_graph,
    reset_course_scaffold_graph_cache,
    run_course_scaffold_graph,
)
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.domain.course_scaffold import (
    FORBIDDEN_BODY_KEYS,
    ScaffoldEdge,
    ScaffoldNode,
    ScaffoldProposal,
    validate_scaffold_proposal,
)

BODY_KEYS = ("readme", "quiz", "project", "questions", "body", "content")


def sample_proposal_payload() -> dict[str, object]:
    return {
        "nodes": [
            {
                "legacy_node_id": "js-root",
                "label": "JavaScript",
                "kind": "root",
                "graph_index": "00",
            },
            {
                "legacy_node_id": "js-mod-1",
                "label": "Foundations",
                "kind": "module",
                "graph_index": "01",
            },
            {
                "legacy_node_id": "js-les-1",
                "label": "Variables",
                "kind": "lesson",
                "graph_index": "01.1",
            },
            {
                "legacy_node_id": "js-mod-2",
                "label": "Functions",
                "kind": "module",
                "graph_index": "02",
            },
            {
                "legacy_node_id": "js-les-2",
                "label": "Arrow functions",
                "kind": "lesson",
                "graph_index": "02.1",
            },
        ],
        "edges": [
            {"parent_legacy_id": "js-root", "child_legacy_id": "js-mod-1", "position": 0},
            {"parent_legacy_id": "js-mod-1", "child_legacy_id": "js-les-1", "position": 0},
            {"parent_legacy_id": "js-root", "child_legacy_id": "js-mod-2", "position": 1},
            {"parent_legacy_id": "js-mod-2", "child_legacy_id": "js-les-2", "position": 0},
        ],
    }


class ScriptedScaffoldModel(BaseChatModel):
    """Returns a valid structure-only JSON proposal."""

    @property
    def _llm_type(self) -> str:
        return "scripted-scaffold"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        payload = json.dumps(sample_proposal_payload())
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=payload))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_registered_workflows_cache()
    reset_course_scaffold_graph_cache()
    reset_workflow_execution_config()
    reset_chat_model()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=1,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )


def test_sample_proposal_is_connected_with_unique_indexes() -> None:
    proposal = ScaffoldProposal.model_validate(sample_proposal_payload())
    assert validate_scaffold_proposal(proposal) == []
    indexes = [node.graph_index for node in proposal.nodes]
    assert len(indexes) == len(set(indexes))
    dumped = proposal.model_dump()
    for node in dumped["nodes"]:
        assert not FORBIDDEN_BODY_KEYS.intersection(key.lower() for key in node)
        for key in BODY_KEYS:
            assert key not in node


def test_scaffold_node_rejects_lesson_body_keys() -> None:
    with pytest.raises(ValidationError):
        ScaffoldNode.model_validate(
            {
                "legacy_node_id": "n1",
                "label": "Variables",
                "kind": "lesson",
                "graph_index": "01.1",
                "readme": "# hello",
            }
        )


def test_disconnected_nodes_fail_validation() -> None:
    proposal = ScaffoldProposal(
        nodes=[
            ScaffoldNode(
                legacy_node_id="a", label="A", kind="root", graph_index="00"
            ),
            ScaffoldNode(
                legacy_node_id="b", label="B", kind="module", graph_index="01"
            ),
        ],
        edges=[],
    )
    findings = validate_scaffold_proposal(proposal)
    assert any("connected" in item for item in findings)


def test_duplicate_graph_index_fails_validation() -> None:
    proposal = ScaffoldProposal(
        nodes=[
            ScaffoldNode(
                legacy_node_id="a", label="A", kind="root", graph_index="00"
            ),
            ScaffoldNode(
                legacy_node_id="b", label="B", kind="module", graph_index="00"
            ),
        ],
        edges=[ScaffoldEdge(parent_legacy_id="a", child_legacy_id="b")],
    )
    findings = validate_scaffold_proposal(proposal)
    assert any("graph_index" in item for item in findings)


def test_course_scaffold_workflow_is_registered() -> None:
    workflow_ids = {workflow.id for workflow in list_registered_workflows()}
    assert "course-scaffold" in workflow_ids


def test_course_scaffold_graph_exposes_generate_and_validate() -> None:
    graph = build_course_scaffold_graph()
    node_ids = set(graph.get_graph().nodes)
    assert "generate" in node_ids
    assert "validate" in node_ids


@pytest.mark.asyncio
async def test_run_course_scaffold_graph_returns_structure_only() -> None:
    set_chat_model(ScriptedScaffoldModel())
    result = await run_course_scaffold_graph(
        tenant_id="00000000-0000-4000-8000-000000000001",
        prompt="Introductory JavaScript course",
        title="JavaScript",
        locale="en",
        slug="javascript",
    )
    proposal = result["proposal"]
    assert isinstance(proposal, ScaffoldProposal)
    assert validate_scaffold_proposal(proposal) == []
    dumped = proposal.model_dump()
    for node in dumped["nodes"]:
        for key in BODY_KEYS:
            assert key not in node
