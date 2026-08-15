"""Domain ports for graph-scoped lesson authoring (E6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class GraphNodeHit(BaseModel):
    """One row from ``search_graph_nodes``."""

    node_id: str
    label: str
    graph_index: str | None = None
    course_slug: str | None = None
    course_title: str | None = None
    kind: str | None = None
    score: float | None = None
    min_word_score: float | None = None


class SaveLessonResult(BaseModel):
    """IDs returned after persisting a lesson bundle."""

    lesson_id: str
    quiz_id: str | None = None
    project_id: str | None = None
    published: bool = False
    catalog_refresh_note: str = (
        "Catalog refresh is enqueued automatically by upsert/publish RPCs (EF3)."
    )


class AuthoringBackendPort(ABC):
    """Persist curriculum artifacts via public PostgREST RPC wrappers."""

    @abstractmethod
    async def upsert_lesson(
        self,
        *,
        module_id: str,
        slug: str,
        title: str,
        description: str | None = None,
        graph_index: str | None = None,
        graph_node_id: str | None = None,
    ) -> str:
        """Return lesson UUID."""

    @abstractmethod
    async def upsert_lesson_content_document(
        self,
        *,
        lesson_id: str,
        readme_markdown: str,
        source_path: str,
    ) -> str:
        """Return content document UUID."""

    @abstractmethod
    async def upsert_quiz_tree(
        self,
        *,
        lesson_id: str,
        quiz: dict[str, Any],
    ) -> str:
        """Return quiz UUID."""

    @abstractmethod
    async def upsert_project_tree(
        self,
        *,
        lesson_id: str,
        project: dict[str, Any],
    ) -> str:
        """Return project UUID."""

    @abstractmethod
    async def publish_lesson(self, *, lesson_id: str) -> dict[str, Any]:
        """Publish lesson and enqueue catalog refresh."""


class GraphSearchPort(ABC):
    """Resolve curriculum graph nodes for grounding."""

    @abstractmethod
    def search_graph_nodes(
        self,
        *,
        tenant_id: str,
        query: str,
        course_slug: str | None = None,
        min_similarity: float = 0.1,
        limit: int = 5,
    ) -> list[GraphNodeHit]:
        ...


MOCK_SECTION_TYPES = ("instructions", "quiz", "coding")


class MockTestSectionSpec(BaseModel):
    """One mock-test section (EF2 ``mock_tests[].sections[]``)."""

    lesson_slug: str = Field(min_length=1)
    position: int = Field(ge=1, le=3)
    section_type: str = Field(pattern=r"^(instructions|quiz|coding)$")
    module_slug: str | None = None


class MockTestBundleEntry(BaseModel):
    """EF2-compatible ``mock_tests[]`` row."""

    module_slug: str = Field(min_length=1)
    duration_minutes: int = Field(default=90, ge=1, le=600)
    passing_score_percent: int = Field(default=70, ge=0, le=100)
    sections: list[MockTestSectionSpec] = Field(min_length=3, max_length=3)


class MockTestStructureResult(BaseModel):
    """Output of ``generate_mock_test_structure`` (E9.2)."""

    mock_test: MockTestBundleEntry
    ef2_fragment: dict[str, Any]
    validation_ok: bool
    validation_messages: list[str] = Field(default_factory=list)


class SaveToBackendRequest(BaseModel):
    """Validated bundle for ``save_to_backend``."""

    manager_jwt: str = Field(min_length=10, description="Manager+ user JWT (Bearer token body)")
    module_id: str = Field(min_length=36, max_length=36)
    lesson_slug: str = Field(min_length=1)
    lesson: dict[str, Any]
    quiz: dict[str, Any] | None = None
    project: dict[str, Any] | None = None
    publish: bool = False
