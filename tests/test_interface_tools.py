"""MCP interface tool contract tests (T20+)."""

import asyncio
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.mcp_tool_cache_runtime import reset_mcp_tool_cache, set_mcp_tool_cache
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.application.workflow_runtime import (
    reset_document_video_workflow,
    set_document_video_workflow,
)
from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRule,
    CacheRuleSet,
    ICacheStore,
)
from mcp_server.domain.exceptions import (
    DomainError,
    DomainValidationError,
    ResourceNotFoundError,
)
from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.infrastructure.mcp_tool_cache import McpToolInteractionCache
from mcp_server.interface.custom_tools import (
    _cached_tool_invoke,
    build_lesson_enrichment_query,
    find_documents,
    health_check,
    search_youtube,
)
from mcp_server.interface.custom_tools_workflow import run_workflow


class InMemoryCacheStore(ICacheStore):
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, key: str) -> bytes | None:
        self.get_calls += 1
        return self.storage.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self.set_calls += 1
        self.storage[key] = value


class FakeRepository:
    async def find_documents(self, query: str, limit: int = 10, *, filters=None) -> list[DocumentHit]:
        return [
            DocumentHit(
                id="doc-1",
                title="Fractions 101",
                content="Full lesson content that must not leak to MCP clients.",
            )
        ]


class FakeVideoClient:
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        return [
            VideoResult(
                title="Fractions Video",
                channel="Edu",
                url="https://example.com/video",
            )
        ]


class FakeChatModel(BaseChatModel):
    response: str = Field(default='["fractions", "numerator", "denominator", "common denominator"]')

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])


@pytest.fixture(autouse=True)
def _reset_tool_runtime() -> None:
    reset_mcp_tool_cache()
    reset_workflow_execution_config()
    reset_document_video_workflow()
    reset_chat_model()
    set_document_video_workflow(DocumentVideoWorkflow(FakeRepository(), FakeVideoClient()))
    yield
    reset_mcp_tool_cache()
    reset_workflow_execution_config()
    reset_document_video_workflow()
    reset_chat_model()


async def test_t20_health_check_returns_ok() -> None:
    assert await health_check() == "ok"


async def test_t21_health_check_uses_tool_cache_on_second_identical_call() -> None:
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.MCP_TOOL: CacheRule(
                operation=CacheOperationType.MCP_TOOL,
                enabled=True,
                ttl_seconds=60,
                key_prefix="mcp",
            )
        }
    )
    set_mcp_tool_cache(McpToolInteractionCache(cache, rules))

    first = await health_check()
    second = await health_check()

    assert first == second == "ok"
    assert cache.set_calls == 1
    assert cache.get_calls >= 2


async def test_t22_search_youtube_returns_validated_response() -> None:
    response = await search_youtube("fractions", max_results=3, language="en")

    assert len(response.videos) == 1
    assert response.videos[0].title == "Fractions Video"


async def test_t23_find_documents_returns_pruned_document_summaries() -> None:
    response = await find_documents("fractions", document_limit=5, video_limit=2)

    assert len(response.documents) == 1
    summary = response.documents[0]
    assert summary.id == "doc-1"
    assert summary.title == "Fractions 101"
    assert "Full lesson content" in summary.snippet
    assert summary.model_dump() == {
        "id": "doc-1",
        "title": "Fractions 101",
        "snippet": "Full lesson content that must not leak to MCP clients.",
    }
    assert "content" not in summary.model_dump()
    assert len(response.videos) == 1


async def test_t24_run_workflow_returns_graph_counts() -> None:
    response = await run_workflow("fractions", document_limit=5, video_limit=2)

    assert response.document_count == 1
    assert response.video_count == 1
    assert response.search_terms == "Fractions 101"
    assert response.documents[0].id == "doc-1"
    assert len(response.videos) == 1


async def test_t25_run_workflow_omits_full_content_from_documents() -> None:
    response = await run_workflow("fractions")

    summary = response.documents[0]
    assert summary.id == "doc-1"
    assert summary.title == "Fractions 101"
    assert "Full lesson content" in summary.snippet
    dumped = summary.model_dump()
    assert set(dumped) == {"id", "title", "snippet"}
    assert "content" not in dumped


async def test_t26_run_workflow_enforces_workflow_timeout() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=0.01,
            agent_node_timeout_seconds=5.0,
        )
    )

    class SlowRepository:
        async def find_documents(self, query: str, limit: int = 10, *, filters=None) -> list[DocumentHit]:
            await asyncio.sleep(0.2)
            return []

    class SlowVideoClient:
        async def search_videos(
            self,
            query: str,
            max_results: int = 5,
            language: str = "en",
            safe_search: bool = True,
        ) -> list[VideoResult]:
            return []

    set_document_video_workflow(DocumentVideoWorkflow(SlowRepository(), SlowVideoClient()))

    with pytest.raises(asyncio.TimeoutError):
        await run_workflow("slow")


async def test_t27_health_check_logs_tool_timing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.interface.custom_tools")

    assert await health_check() == "ok"

    assert "mcp tool tool=health_check" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "outcome=success" in caplog.text


async def test_t28_cached_tool_invoke_logs_error_outcome(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.interface.custom_tools")

    async def failing_invoker() -> str:
        raise ValueError("tool failed")

    with pytest.raises(ValueError, match="tool failed"):
        await _cached_tool_invoke("health_check", {}, failing_invoker)

    assert "mcp tool tool=health_check" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "outcome=error" in caplog.text
    assert "outcome=success" not in caplog.text


async def test_t29_cached_tool_invoke_maps_resource_not_found_to_fastmcp_error() -> None:
    from fastmcp.exceptions import NotFoundError as FastMcpNotFoundError

    async def not_found_invoker() -> str:
        raise ResourceNotFoundError("YouTube API credentials are not configured")

    with pytest.raises(FastMcpNotFoundError, match="YouTube API credentials"):
        await _cached_tool_invoke("search_youtube", {}, not_found_invoker)


async def test_t30_cached_tool_invoke_maps_domain_validation_to_mcp_error() -> None:
    from mcp import McpError

    async def validation_invoker() -> str:
        raise DomainValidationError("query must not be empty")

    with pytest.raises(McpError, match="Invalid params: query must not be empty"):
        await _cached_tool_invoke("find_documents", {}, validation_invoker)


async def test_t31_raise_as_mcp_error_maps_generic_domain_error_to_tool_error() -> None:
    from fastmcp.exceptions import ToolError

    from mcp_server.interface.error_mapping import raise_as_mcp_error

    class OtherDomainError(DomainError):
        pass

    with pytest.raises(ToolError, match="unexpected domain failure"):
        raise_as_mcp_error(OtherDomainError("unexpected domain failure"))


async def test_t32_uninitialized_workflow_maps_to_not_found_error() -> None:
    from fastmcp.exceptions import NotFoundError as FastMcpNotFoundError

    reset_document_video_workflow()

    with pytest.raises(FastMcpNotFoundError, match="Document video workflow"):
        await find_documents("fractions")


async def test_t33_build_lesson_enrichment_query_returns_terms_and_query() -> None:
    set_chat_model(FakeChatModel())

    response = await build_lesson_enrichment_query(
        course_title="Mathematics",
        module_title="Fractions",
        lesson_title="Adding fractions",
    )

    assert response.terms == [
        "fractions",
        "numerator",
        "denominator",
        "common",
        "mathematics",
    ]
    assert response.query == "fractions numerator denominator common mathematics"


async def test_t34_build_lesson_enrichment_query_falls_back_to_titles() -> None:
    set_chat_model(FakeChatModel(response="not a json array"))

    response = await build_lesson_enrichment_query(
        course_title="Mathematics",
        module_title="Basic Fractions",
        lesson_title="Adding Fractions",
    )

    assert response.terms == ["mathematics", "basic", "fractions", "adding"]
    assert response.query == "mathematics basic fractions adding"
