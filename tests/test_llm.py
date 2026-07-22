"""LLM factory, cache wrapper, and agent policy contract tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import SecretStr

from mcp_server.application.agent import (
    _node_retry_policy,
    _node_timeout_seconds,
    _read_node_retry_policy,
    ainvoke_with_workflow_timeout,
    build_document_video_graph,
    initial_document_video_state,
    run_document_video_graph,
    workflow_timeout_seconds,
)
from mcp_server.application.llm import (
    create_chat_model,
    get_chat_model,
    register_groq_model_builder,
    reset_chat_model,
    reset_groq_model_builder,
    set_chat_model,
)
from mcp_server.application.llm_models import resolve_language_model
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.application.workflow_runtime import (
    get_document_video_workflow,
    reset_document_video_workflow,
    set_document_video_workflow,
)
from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.cache import CacheOperationType, CacheRule, CacheRuleSet, ICacheStore
from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.infrastructure.cached_llm import CachedChatModel
from mcp_server.settings import load_settings
from mcp_server.wiring import (
    build_chat_model,
    build_document_video_workflow,
    initialize_application_runtime,
)


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


class StubChatModel(BaseChatModel):
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        StubChatModel.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="stub-response"))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        StubChatModel.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="stub-response"))])


@pytest.fixture(autouse=True)
def _reset_llm_runtime() -> None:
    reset_groq_model_builder()
    reset_chat_model()
    reset_workflow_execution_config()
    reset_document_video_workflow()
    StubChatModel.calls = 0


def _stub_groq_builder(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
    _ = api_key, model_id, temperature
    return StubChatModel()


def test_llm01_create_chat_model_requires_groq_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    register_groq_model_builder(_stub_groq_builder)
    settings = load_settings()

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        create_chat_model(settings)


def test_llm02_create_chat_model_uses_registered_groq_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    register_groq_model_builder(_stub_groq_builder)
    settings = load_settings()

    model = create_chat_model(settings, model_id="llama-3.1-8b-instant", temperature=0.5)

    assert isinstance(model, StubChatModel)


def test_llm03_resolve_language_model_returns_groq_spec() -> None:
    spec = resolve_language_model("mixtral-8x7b-32768")
    assert spec["provider"] == "groq"


async def test_llm04_cached_chat_model_hits_cache_on_second_ainvoke() -> None:
    inner = StubChatModel()
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.LLM_COMPLETION: CacheRule(
                operation=CacheOperationType.LLM_COMPLETION,
                enabled=True,
                ttl_seconds=600,
                key_prefix="llm",
            )
        }
    )
    model = CachedChatModel(inner, cache, rules, model_name="llama-3.3-70b-versatile")

    first = await model.ainvoke("hello")
    second = await model.ainvoke("hello")

    assert first.content == second.content == "stub-response"
    assert StubChatModel.calls == 1
    assert cache.set_calls == 1
    assert cache.get_calls >= 2


def test_llm04b_cached_chat_model_sync_generate_bypasses_cache() -> None:
    inner = StubChatModel()
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.LLM_COMPLETION: CacheRule(
                operation=CacheOperationType.LLM_COMPLETION,
                enabled=True,
                ttl_seconds=600,
                key_prefix="llm",
            )
        }
    )
    model = CachedChatModel(inner, cache, rules, model_name="llama-3.3-70b-versatile")
    messages = [HumanMessage(content="hello")]

    first = model._generate(messages)
    second = model._generate(messages)

    assert first.generations[0].message.content == "stub-response"
    assert second.generations[0].message.content == "stub-response"
    assert StubChatModel.calls == 2
    assert cache.get_calls == 0
    assert cache.set_calls == 0


def test_llm05_agent_nodes_use_workflow_execution_config() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=2,
            workflow_timeout_seconds=120.0,
            agent_node_timeout_seconds=15.0,
        )
    )

    retry_policy = _node_retry_policy()
    read_retry_policy = _read_node_retry_policy()
    assert retry_policy.max_attempts == 3
    assert read_retry_policy.max_attempts == 2
    assert _node_timeout_seconds() == 15.0
    assert workflow_timeout_seconds() == 120.0

    graph = build_document_video_graph()
    assert graph is not None


class _GraphFakeRepository:
    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        return [DocumentHit(id="1", title=query, content="body")]


class _GraphFakeVideoClient:
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        return [VideoResult(title="Video", channel="Ch", url="https://example.com")]


async def test_llm05b_graph_nodes_delegate_to_document_video_workflow() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=1,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=5.0,
        )
    )
    workflow = DocumentVideoWorkflow(_GraphFakeRepository(), _GraphFakeVideoClient())
    set_document_video_workflow(workflow)

    result = await run_document_video_graph("algebra", document_limit=2, video_limit=3)

    assert result["document_count"] == 1
    assert result["video_count"] == 1
    assert result["search_terms"] == "algebra"
    assert result["documents"][0].title == "algebra"


def test_llm05d_graph_has_delegation_nodes_not_skeleton() -> None:
    graph = build_document_video_graph()
    node_names = set(graph.get_graph().nodes.keys()) - {"__start__", "__end__"}

    assert node_names == {
        "fetch_documents",
        "derive_search_terms",
        "search_videos",
        "merge_results",
    }
    assert not any(name.startswith("_count_") for name in node_names)


async def test_llm05c_workflow_timeout_enforced() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=0.01,
            agent_node_timeout_seconds=5.0,
        )
    )

    class SlowRepository:
        async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
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

    workflow = DocumentVideoWorkflow(SlowRepository(), SlowVideoClient())
    set_document_video_workflow(workflow)
    graph = build_document_video_graph()
    state = initial_document_video_state("slow")

    with pytest.raises(asyncio.TimeoutError):
        await ainvoke_with_workflow_timeout(graph, state)


def test_llm06_initialize_application_runtime_defers_chat_model_until_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_server.operational_config import OperationalConfig

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    operational = OperationalConfig(
        node_retries=1,
        workflow_timeout=60,
        agent_node_timeout=30,
    )
    settings = load_settings()
    build_calls = 0
    original_build = build_chat_model

    def _counting_build(
        settings_arg: object,
        cache: object | None = None,
    ) -> BaseChatModel:
        nonlocal build_calls
        build_calls += 1
        return original_build(settings_arg, cache)  # type: ignore[arg-type]

    monkeypatch.setattr("mcp_server.wiring.build_chat_model", _counting_build)

    initialize_application_runtime(operational, settings)
    assert build_calls == 0

    model = get_chat_model()
    assert build_calls == 1
    assert model is not None


def test_llm06b_initialize_application_runtime_defers_workflow_until_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_server.operational_config import OperationalConfig

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    operational = OperationalConfig(
        node_retries=1,
        workflow_timeout=60,
        agent_node_timeout=30,
    )
    settings = load_settings()
    build_calls = 0
    original_build = build_document_video_workflow

    def _counting_build(
        settings_arg: object,
        cache: object | None = None,
    ) -> DocumentVideoWorkflow:
        nonlocal build_calls
        build_calls += 1
        return original_build(settings_arg, cache)  # type: ignore[arg-type]

    monkeypatch.setattr("mcp_server.wiring.build_document_video_workflow", _counting_build)

    initialize_application_runtime(operational, settings)
    assert build_calls == 0

    workflow = get_document_video_workflow()
    assert build_calls == 1
    assert workflow is not None
    reset_document_video_workflow()


async def test_llm04c_cached_chat_model_parallel_misses_invoke_inner_once() -> None:
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.LLM_COMPLETION: CacheRule(
                operation=CacheOperationType.LLM_COMPLETION,
                enabled=True,
                ttl_seconds=600,
                key_prefix="llm",
            )
        }
    )
    model = CachedChatModel(StubChatModel(), cache, rules, model_name="llama-3.3-70b-versatile")

    class SlowStubChatModel(StubChatModel):
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            await asyncio.sleep(0.05)
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

    model._inner = SlowStubChatModel()  # type: ignore[attr-defined]
    StubChatModel.calls = 0

    await asyncio.gather(*[model._agenerate([HumanMessage(content="hello")]) for _ in range(8)])

    assert StubChatModel.calls == 1
    assert cache.set_calls == 1


def test_llm05e_graph_derive_and_merge_nodes_use_read_retry_policy(monkeypatch) -> None:
    from langgraph.graph import StateGraph

    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=3,
            workflow_timeout_seconds=120.0,
            agent_node_timeout_seconds=15.0,
        )
    )

    read_retry_policy = _read_node_retry_policy()
    node_policies: dict[str, object] = {}
    original_add_node = StateGraph.add_node

    def spy_add_node(self, node, action, **kwargs):
        if "retry_policy" in kwargs:
            node_policies[node] = kwargs["retry_policy"]
        return original_add_node(self, node, action, **kwargs)

    monkeypatch.setattr(StateGraph, "add_node", spy_add_node)
    build_document_video_graph()

    assert node_policies["derive_search_terms"].max_attempts == read_retry_policy.max_attempts
    assert node_policies["merge_results"].max_attempts == read_retry_policy.max_attempts


def test_llm07_build_chat_model_wraps_with_cache_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("CACHE_ENABLED", "true")

    settings = load_settings()
    model = build_chat_model(settings, InMemoryCacheStore())

    assert type(model).__name__ == "CachedChatModel"


def test_llm07b_build_chat_model_requires_cache_store_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("CACHE_ENABLED", "true")

    settings = load_settings()
    with pytest.raises(ValueError, match="cache store is required"):
        build_chat_model(settings)


def test_llm08_set_chat_model_runtime_accessor() -> None:
    model = StubChatModel()
    set_chat_model(model)
    assert get_chat_model() is model


def test_llm09_resolve_language_model_unknown_id_raises() -> None:
    with pytest.raises(ValueError, match="Unknown language model id"):
        resolve_language_model("nonexistent-model")


def test_llm10_create_chat_model_unsupported_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    register_groq_model_builder(_stub_groq_builder)
    settings = load_settings()

    with pytest.raises(ValueError, match="Unsupported language model provider"):
        create_chat_model(settings, model_id="gpt-4o")


def test_llm11_create_chat_model_unregistered_builder_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    settings = load_settings()

    with pytest.raises(RuntimeError, match="Groq model builder has not been registered"):
        create_chat_model(settings)


def test_llm12_default_workflow_execution_config_matches_config_json() -> None:
    import json
    from pathlib import Path

    from mcp_server.application.workflow_config import DEFAULT_WORKFLOW_EXECUTION_CONFIG

    config_path = Path(__file__).resolve().parents[1] / "config.json"
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    assert DEFAULT_WORKFLOW_EXECUTION_CONFIG.node_retries == raw["node_retries"]
    assert DEFAULT_WORKFLOW_EXECUTION_CONFIG.workflow_timeout_seconds == raw["workflow_timeout"]
    assert DEFAULT_WORKFLOW_EXECUTION_CONFIG.agent_node_timeout_seconds == raw["agent_node_timeout"]
