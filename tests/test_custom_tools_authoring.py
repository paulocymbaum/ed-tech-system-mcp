"""Tests for authoring MCP tools and mock-test structure (E9)."""

from __future__ import annotations

from typing import Any

import pytest

from mcp_server.application.mock_test_authoring import build_mock_test_structure
from mcp_server.domain.authoring import GraphNodeHit, GraphSearchPort
from mcp_server.domain.content_validators import validate_mock_test_bundle
from mcp_server.infrastructure.authoring_backend_client import AuthoringBackendClientFactory
from mcp_server.interface.custom_tools_authoring import (
    generate_mock_test_structure,
    register_authoring_tools,
    search_graph_nodes,
    validate_mock_test,
)


class FakeGraphSearch(GraphSearchPort):
    def search_graph_nodes(
        self,
        *,
        tenant_id: str,
        query: str,
        course_slug: str | None = None,
        min_similarity: float = 0.1,
        limit: int = 5,
    ) -> list[GraphNodeHit]:
        assert tenant_id
        assert query.strip()
        return [
            GraphNodeHit(
                node_id="node-1",
                label="Binary Search",
                graph_index="03.2.1",
                course_slug=course_slug,
                kind="lesson",
                score=0.72,
            )
        ]


class FakeBackendFactory(AuthoringBackendClientFactory):
    def __init__(self) -> None:
        pass

    def for_jwt(self, manager_jwt: str) -> Any:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _register_authoring() -> None:
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_search_graph_nodes_delegates_to_repository() -> None:
    response = await search_graph_nodes(
        tenant_id="00000000-0000-4000-8000-000000000001",
        query="binary search",
        course_slug="javascript",
        limit=3,
    )
    assert response.query == "binary search"
    assert len(response.results) == 1
    assert response.results[0].graph_index == "03.2.1"


def test_validate_mock_test_bundle_accepts_standard_shape() -> None:
    payload = build_mock_test_structure(study_module_slug="01-javascript-fundamentals").mock_test
    report = validate_mock_test_bundle(payload.model_dump())
    assert report.ok is True


def test_validate_mock_test_bundle_rejects_wrong_section_order() -> None:
    report = validate_mock_test_bundle(
        {
            "module_slug": "01-javascript-fundamentals-mock",
            "duration_minutes": 90,
            "passing_score_percent": 70,
            "sections": [
                {"lesson_slug": "a", "position": 1, "section_type": "quiz"},
                {"lesson_slug": "b", "position": 2, "section_type": "instructions"},
                {"lesson_slug": "c", "position": 3, "section_type": "coding"},
            ],
        }
    )
    assert report.ok is False
    assert any("instructions" in f.message for f in report.errors)


@pytest.mark.asyncio
async def test_generate_mock_test_structure_returns_ef2_fragment() -> None:
    result = await generate_mock_test_structure(
        study_module_slug="01-javascript-fundamentals",
        duration_minutes=60,
    )
    assert result.validation_ok is True
    assert result.mock_test.module_slug == "01-javascript-fundamentals-mock"
    assert len(result.mock_test.sections) == 3
    assert result.ef2_fragment["mock_tests"][0]["module_slug"].endswith("-mock")


@pytest.mark.asyncio
async def test_validate_mock_test_tool() -> None:
    good = build_mock_test_structure(study_module_slug="02-async").mock_test.model_dump()
    response = await validate_mock_test(good)
    assert response.ok is True

    bad = {**good, "sections": good["sections"][:2]}
    response_bad = await validate_mock_test(bad)
    assert response_bad.ok is False
