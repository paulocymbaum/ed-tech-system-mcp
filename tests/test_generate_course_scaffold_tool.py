"""Auth and happy-path tests for generate_course_scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from mcp_server.application.course_scaffold_runner import invoke_course_scaffold
from mcp_server.application.mcp_tool_auth_runtime import (
    PRIVILEGED_TOOLS,
    McpToolAuthRuntime,
    set_mcp_tool_auth_runtime,
)
from mcp_server.application.workflow_trace import GraphStreamComplete, WorkflowTraceStart
from mcp_server.domain.ai_generation_job import AiGenerationJobProgressPort, AiGenerationJobSnapshot
from mcp_server.domain.authoring import (
    AuthoringBackendFactoryPort,
    AuthoringBackendPort,
    GraphSearchPort,
)
from mcp_server.domain.course_scaffold import ScaffoldProposal
from mcp_server.domain.exceptions import DomainAuthorizationError, DomainValidationError
from mcp_server.interface.custom_tools_authoring import (
    generate_course_scaffold,
    register_authoring_tools,
)
from mcp_server.interface.privileged_tool_auth import _enforce_caller


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


class FakeGraphSearch(GraphSearchPort):
    def search_graph_nodes(self, **kwargs: Any) -> list[Any]:
        del kwargs
        return []


class FakeBackendFactory(AuthoringBackendFactoryPort):
    def for_jwt(self, manager_jwt: str) -> AuthoringBackendPort:
        raise NotImplementedError


@dataclass
class RecordingJobProgress(AiGenerationJobProgressPort):
    updates: list[dict[str, Any]] = field(default_factory=list)

    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        del job_id
        return None

    async def update(
        self,
        *,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error: str | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        self.updates.append(
            {
                "job_id": job_id,
                "status": status,
                "phase": phase,
                "error": error,
                "result_ref": result_ref,
            }
        )


@dataclass
class FakeIdentity:
    user_id: str = "user-1"
    members: frozenset[tuple[str, str]] = frozenset({("user-1", "tenant-1")})

    def user_id_from_jwt(self, caller_jwt: str) -> str:
        if caller_jwt != "valid-jwt":
            raise DomainAuthorizationError("Could not verify caller")
        return self.user_id

    def is_tenant_member(self, *, user_id: str, tenant_id: str) -> bool:
        return (user_id, tenant_id) in self.members


@pytest.fixture(autouse=True)
def _register_authoring() -> None:
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=None,
    )


def test_generate_course_scaffold_is_privileged() -> None:
    assert "generate_course_scaffold" in PRIVILEGED_TOOLS
    assert "search_web" in PRIVILEGED_TOOLS


async def test_enforce_caller_rejects_manager_jwt_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.privileged_tool_auth._caller_jwt_from_headers",
        lambda: "valid-jwt",
    )
    runtime = McpToolAuthRuntime(require_caller_jwt=True, identity=FakeIdentity())
    with pytest.raises(DomainAuthorizationError, match="manager_jwt"):
        await _enforce_caller(
            runtime,
            "generate_course_scaffold",
            {
                "manager_jwt": "other-jwt",
                "tenant_id": "tenant-1",
                "prompt": "outline",
            },
        )


async def test_enforce_caller_accepts_matching_manager_and_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mcp_server.interface.privileged_tool_auth._caller_jwt_from_headers",
        lambda: "valid-jwt",
    )
    runtime = McpToolAuthRuntime(require_caller_jwt=True, identity=FakeIdentity())
    set_mcp_tool_auth_runtime(runtime)
    await _enforce_caller(
        runtime,
        "generate_course_scaffold",
        {
            "manager_jwt": "valid-jwt",
            "tenant_id": "tenant-1",
            "prompt": "outline",
        },
    )


@pytest.mark.asyncio
async def test_generate_course_scaffold_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    proposal = ScaffoldProposal.model_validate(sample_proposal_payload())
    progress = RecordingJobProgress()
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )

    async def _fake_invoke(**kwargs: Any) -> ScaffoldProposal:
        assert kwargs["tenant_id"] == "tenant-1"
        assert kwargs["prompt"] == "Teach JS"
        assert kwargs["job_id"] == "job-1"
        assert kwargs["job_progress"] is progress
        return proposal

    monkeypatch.setattr(
        "mcp_server.interface.custom_tools_authoring.invoke_course_scaffold",
        _fake_invoke,
    )
    response = await generate_course_scaffold(
        manager_jwt="valid-jwt-token",
        tenant_id="tenant-1",
        prompt="Teach JS",
        title="JavaScript",
        locale="en",
        slug="javascript",
        job_id="job-1",
    )
    assert len(response.nodes) == 5
    assert response.nodes[0].kind == "root"
    assert all(
        key not in node.model_dump()
        for node in response.nodes
        for key in ("readme", "quiz", "project")
    )
    assert {edge.parent_legacy_id for edge in response.edges}


@pytest.mark.asyncio
async def test_generate_course_scaffold_requires_prompt() -> None:
    with pytest.raises(DomainValidationError, match="prompt"):
        await generate_course_scaffold(
            manager_jwt="valid-jwt-token",
            tenant_id="tenant-1",
            prompt="   ",
            title="JavaScript",
            locale="en",
            slug="javascript",
        )


@pytest.mark.asyncio
async def test_invoke_course_scaffold_reports_generate_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = ScaffoldProposal.model_validate(sample_proposal_payload())
    progress = RecordingJobProgress()

    async def _stream(graph: Any, state: Any, **kwargs: Any):
        del graph, state, kwargs
        yield WorkflowTraceStart(node_id="generate")
        yield GraphStreamComplete(
            state={"proposal": proposal, "validation_errors": []},
            trace=[],
        )

    monkeypatch.setattr(
        "mcp_server.application.course_scaffold_runner.stream_graph_with_trace",
        _stream,
    )
    result = await invoke_course_scaffold(
        tenant_id="tenant-1",
        prompt="Teach JS",
        title="JavaScript",
        locale="en",
        slug="javascript",
        job_id="job-9",
        job_progress=progress,
    )
    assert result.nodes[0].legacy_node_id == "js-root"
    phases = [item["phase"] for item in progress.updates]
    statuses = [item["status"] for item in progress.updates]
    assert "generate" in phases
    assert "running" in statuses
    assert "succeeded" not in statuses
