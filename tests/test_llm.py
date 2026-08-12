"""LLM factory, cache wrapper, and agent policy contract tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
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
    register_llm_router,
    reset_chat_model,
    reset_groq_model_builder,
    reset_llm_router,
    set_chat_model,
)
from mcp_server.application.llm_models import (
    register_groq_language_models,
    reset_groq_language_models,
    resolve_language_model,
)
from mcp_server.application.llm_router import LLMRouter, is_token_limit_error
from mcp_server.application.routing_chat_model import RoutingChatModel
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
from mcp_server.domain.llm_routing import (
    GroqModelCatalogEntry,
    GroqModelPricing,
    GroqModelRecord,
    IGroqModelCatalogClient,
    IGroqModelRegistry,
    ILLMDebounceGate,
    LLMComplexity,
    is_developer_plan_groq_model,
    is_free_groq_model_pricing,
    token_limit_deactivation_until,
)
from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.infrastructure.cached_llm import CachedChatModel
from mcp_server.infrastructure.llm_debounce import IntervalLLMDebounceGate
from mcp_server.settings import load_settings
from mcp_server.wiring import (
    build_chat_model,
    build_document_video_workflow,
    initialize_application_runtime,
    reset_wired_llm_router,
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
    reset_llm_router()
    reset_wired_llm_router()
    reset_groq_language_models()
    reset_chat_model()
    reset_workflow_execution_config()
    reset_document_video_workflow()
    StubChatModel.calls = 0


def _chat_catalog_entry(
    model_id: str,
    *,
    pricing: GroqModelPricing | None | object = ...,
    display_name: str | None = None,
) -> GroqModelCatalogEntry:
    resolved_pricing: GroqModelPricing | None
    if pricing is ...:
        resolved_pricing = GroqModelPricing()
    else:
        resolved_pricing = pricing  # type: ignore[assignment]
    return GroqModelCatalogEntry(
        model_id=model_id,
        display_name=display_name or model_id,
        input_modalities=("text",),
        output_modalities=("text",),
        pricing=resolved_pricing,
    )


class StaticGroqModelCatalog(IGroqModelCatalogClient):
    def __init__(self, entries: list[GroqModelCatalogEntry]) -> None:
        self._entries = entries

    def fetch_models(self) -> list[GroqModelCatalogEntry]:
        return list(self._entries)


class InMemoryGroqModelRegistry(IGroqModelRegistry):
    def __init__(
        self,
        model_ids: list[str],
        *,
        free: bool = True,
        complexity_by_id: dict[str, frozenset[int]] | None = None,
    ) -> None:
        self._records = {
            model_id: GroqModelRecord(
                model_id=model_id,
                display_name=model_id,
                active=free,
                is_free=free,
                is_developer_plan=is_developer_plan_groq_model(model_id),
                is_routable=True,
                complexity=(
                    complexity_by_id.get(model_id, frozenset({2}))
                    if complexity_by_id
                    else frozenset({2})
                ),
            )
            for model_id in model_ids
        }

    def refresh_active_models(self) -> None:
        return

    def refresh_from_catalog(self) -> None:
        return

    def list_records(self) -> list[GroqModelRecord]:
        return list(self._records.values())

    def get_active_model_ids(self) -> list[str]:
        return sorted(record.model_id for record in self._records.values() if record.active)

    def get_active_model_ids_for_complexity(self, complexity: LLMComplexity) -> list[str]:
        tier = int(complexity)
        return sorted(
            record.model_id
            for record in self._records.values()
            if record.active and tier in record.complexity
        )

    def deactivate_until(self, model_id: str, until: datetime) -> None:
        record = self._records.get(model_id)
        if record is None:
            return
        self._records[model_id] = GroqModelRecord(
            model_id=model_id,
            display_name=record.display_name,
            active=False,
            is_free=record.is_free,
            is_developer_plan=record.is_developer_plan,
            is_routable=record.is_routable,
            deactivated_until=until,
            complexity=record.complexity,
        )

    def is_known_model(self, model_id: str) -> bool:
        return model_id in self._records


class NoOpDebounceGate(ILLMDebounceGate):
    def acquire_sync(self) -> None:
        return

    async def acquire(self) -> None:
        return


def _stub_groq_builder(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
    _ = api_key, model_id, temperature
    return StubChatModel()


def _register_test_router(
    model_ids: list[str],
    *,
    api_key: SecretStr | None = None,
    complexity_by_id: dict[str, frozenset[int]] | None = None,
) -> LLMRouter:
    key = api_key or SecretStr("groq-test-key")
    register_groq_model_builder(_stub_groq_builder)
    register_groq_language_models(
        [
            GroqModelRecord(
                model_id=model_id,
                display_name=model_id,
                active=True,
                is_free=True,
                is_developer_plan=is_developer_plan_groq_model(model_id),
                is_routable=True,
                complexity=(
                    complexity_by_id.get(model_id, frozenset({2}))
                    if complexity_by_id
                    else frozenset({2})
                ),
            )
            for model_id in model_ids
        ]
    )
    registry = InMemoryGroqModelRegistry(model_ids, complexity_by_id=complexity_by_id)
    router = LLMRouter(
        api_key=key,
        temperature=0.0,
        registry=registry,
        debounce_gate=NoOpDebounceGate(),
        model_builder=_stub_groq_builder,
        default_complexity=LLMComplexity.MEDIUM,
    )
    register_llm_router(router)
    return router


def _patch_groq_catalog_for_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp_server.domain.llm_routing import GroqActiveModel

    models = [
        GroqActiveModel(model_id="llama-3.1-8b-instant", complexity=frozenset({1, 2})),
        GroqActiveModel(model_id="llama-3.3-70b-versatile", complexity=frozenset({2, 3})),
        GroqActiveModel(model_id="mixtral-8x7b-32768", complexity=frozenset({2})),
    ]

    def _fake_fetch(self: object) -> list[GroqActiveModel]:
        _ = self
        return list(models)

    monkeypatch.setattr(
        "mcp_server.infrastructure.groq_active_model_list_client"
        ".SupabaseGroqActiveModelListClient.fetch_active_models",
        _fake_fetch,
    )


def test_llm01_create_chat_model_requires_groq_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    _register_test_router(["llama-3.3-70b-versatile"])
    settings = load_settings()

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        create_chat_model(settings)


def test_llm02_create_chat_model_uses_registered_groq_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    _register_test_router(["llama-3.1-8b-instant", "llama-3.3-70b-versatile"])
    settings = load_settings()

    model = create_chat_model(settings, model_id="llama-3.1-8b-instant", temperature=0.5)

    assert isinstance(model, RoutingChatModel)
    assert model._router._temperature == 0.5  # noqa: SLF001


def test_llm03_resolve_language_model_returns_groq_spec() -> None:
    register_groq_language_models(
        [
            GroqModelRecord(
                model_id="allam-2-7b",
                display_name="Allam 2 7B",
                active=True,
                is_free=True,
                is_developer_plan=False,
                is_routable=True,
            )
        ]
    )
    spec = resolve_language_model("allam-2-7b")
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
    assert read_retry_policy.max_attempts == 1
    assert _node_timeout_seconds() == 15.0
    assert workflow_timeout_seconds() == 120.0

    graph = build_document_video_graph()
    assert graph is not None


class _GraphFakeRepository:
    def __init__(self) -> None:
        self.last_filters = None

    async def find_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        filters=None,
    ) -> list[DocumentHit]:
        self.last_filters = filters
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


async def test_llm05b_graph_forwards_tenant_id_to_repository() -> None:
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=1,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=5.0,
        )
    )
    repository = _GraphFakeRepository()
    workflow = DocumentVideoWorkflow(repository, _GraphFakeVideoClient())
    set_document_video_workflow(workflow)
    tenant_id = "8d9cad71-55db-43e4-87f3-89b9077c174f"

    await run_document_video_graph(
        "algebra",
        document_limit=2,
        video_limit=3,
        tenant_id=tenant_id,
    )

    assert repository.last_filters is not None
    assert repository.last_filters.tenant_id == tenant_id


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
        async def find_documents(
            self,
            query: str,
            limit: int = 10,
            *,
            filters=None,
        ) -> list[DocumentHit]:
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
    _patch_groq_catalog_for_wiring(monkeypatch)

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
    _patch_groq_catalog_for_wiring(monkeypatch)

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
    _patch_groq_catalog_for_wiring(monkeypatch)

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
    _register_test_router(["llama-3.3-70b-versatile"])
    settings = load_settings()

    with pytest.raises(ValueError, match="Unsupported language model provider"):
        create_chat_model(settings, model_id="gpt-4o")


def test_llm11_create_chat_model_unregistered_builder_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    register_groq_language_models(
        [
            GroqModelRecord(
                model_id="llama-3.3-70b-versatile",
                display_name="Llama 3.3 70B Versatile",
                active=True,
                is_free=True,
                is_developer_plan=True,
                is_routable=True,
            )
        ]
    )
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


def test_llm13_router_maps_complexity_to_model_tiers() -> None:
    router = _register_test_router(
        ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"],
        complexity_by_id={
            "llama-3.1-8b-instant": frozenset({1, 2}),
            "mixtral-8x7b-32768": frozenset({2}),
            "llama-3.3-70b-versatile": frozenset({2, 3}),
        },
    )

    low = router.candidate_model_ids(LLMComplexity.LOW)
    medium = router.candidate_model_ids(LLMComplexity.MEDIUM)
    high = router.candidate_model_ids(LLMComplexity.HIGH)

    assert low == ["llama-3.1-8b-instant"]
    assert medium == [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
    ]
    assert high == ["llama-3.3-70b-versatile"]


def test_llm13b_router_falls_back_to_medium_when_tier_empty() -> None:
    router = _register_test_router(
        ["llama-3.3-70b-versatile"],
        complexity_by_id={"llama-3.3-70b-versatile": frozenset({2, 3})},
    )

    low = router.candidate_model_ids(LLMComplexity.LOW)

    assert low == ["llama-3.3-70b-versatile"]


def test_llm14_router_falls_back_on_provider_failure() -> None:
    class FailingThenOkModel(BaseChatModel):
        model_id: str
        fail: bool = False

        @property
        def _llm_type(self) -> str:
            return "failing-stub"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            if self.fail:
                raise RuntimeError("provider unavailable")
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=self.model_id))]
            )

        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def builder(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
        _ = api_key, temperature
        return FailingThenOkModel(model_id=model_id, fail=model_id == "llama-3.1-8b-instant")

    register_groq_model_builder(builder)
    registry = InMemoryGroqModelRegistry(
        ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        complexity_by_id={
            "llama-3.1-8b-instant": frozenset({1, 2}),
            "llama-3.3-70b-versatile": frozenset({1, 2}),
        },
    )
    router = LLMRouter(
        api_key=SecretStr("test"),
        temperature=0.0,
        registry=registry,
        debounce_gate=NoOpDebounceGate(),
        model_builder=builder,
        default_complexity=LLMComplexity.LOW,
    )

    result = router.generate([HumanMessage(content="hello")])

    assert result.generations[0].message.content == "llama-3.3-70b-versatile"


def test_llm15_token_limit_error_deactivates_model_for_three_hours() -> None:
    registry = InMemoryGroqModelRegistry(["llama-3.3-70b-versatile"])
    until = datetime.now(tz=UTC) + timedelta(hours=3)

    class TokenLimitModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "token-limit-stub"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            raise RuntimeError("context_length_exceeded")

        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def builder(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
        _ = api_key, model_id, temperature
        return TokenLimitModel()

    router = LLMRouter(
        api_key=SecretStr("test"),
        temperature=0.0,
        registry=registry,
        debounce_gate=NoOpDebounceGate(),
        model_builder=builder,
        default_complexity=LLMComplexity.MEDIUM,
    )

    with pytest.raises(RuntimeError, match="context_length"):
        router.generate([HumanMessage(content="hello")])

    record = registry.list_records()[0]
    assert record.active is False
    assert record.deactivated_until is not None
    assert record.deactivated_until >= until - timedelta(seconds=5)


def test_llm16_is_token_limit_error_detects_context_length() -> None:
    assert is_token_limit_error(RuntimeError("context_length_exceeded"))
    assert not is_token_limit_error(RuntimeError("network timeout"))


async def test_llm17_debounce_gate_spaces_async_calls() -> None:
    gate = IntervalLLMDebounceGate(0.05)
    start = asyncio.get_event_loop().time()
    await gate.acquire()
    await gate.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.04


def test_llm17b_debounce_gate_spaces_sync_calls() -> None:
    import time

    gate = IntervalLLMDebounceGate(0.05)
    start = time.monotonic()
    gate.acquire_sync()
    gate.acquire_sync()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.04


def test_llm18_groq_registry_loads_active_models_with_complexity() -> None:
    from mcp_server.domain.llm_routing import GroqActiveModel
    from mcp_server.infrastructure.groq_model_registry import GroqModelRegistry

    class StaticList:
        def fetch_active_models(self) -> list[GroqActiveModel]:
            return [
                GroqActiveModel("llama-3.1-8b-instant", frozenset({1, 2})),
                GroqActiveModel("llama-3.3-70b-versatile", frozenset({2, 3})),
            ]

    registry = GroqModelRegistry(StaticList())  # type: ignore[arg-type]
    registry.refresh_active_models()
    records = {record.model_id: record for record in registry.list_records()}

    assert records["llama-3.1-8b-instant"].active is True
    assert records["llama-3.1-8b-instant"].complexity == frozenset({1, 2})
    assert registry.get_active_model_ids_for_complexity(LLMComplexity.LOW) == [
        "llama-3.1-8b-instant"
    ]
    assert registry.get_active_model_ids_for_complexity(LLMComplexity.HIGH) == [
        "llama-3.3-70b-versatile"
    ]


def test_llm18b_is_free_groq_model_pricing_requires_zero_rates() -> None:
    assert is_free_groq_model_pricing(GroqModelPricing()) is True
    assert is_free_groq_model_pricing(None) is True
    assert is_free_groq_model_pricing(GroqModelPricing(prompt=5e-8)) is False


def test_llm18c_parse_active_models_payload_skips_invalid_rows() -> None:
    from mcp_server.domain.llm_routing import GroqActiveModel
    from mcp_server.infrastructure.groq_active_model_list_client import parse_active_models_payload

    parsed = parse_active_models_payload(
        [
            {"model_id": "ok", "complexity": [1, 2]},
            {"model_id": "", "complexity": [2]},
            {"model_id": "bad-tier", "complexity": [9]},
            {"model_id": "missing"},
        ]
    )
    assert parsed == [GroqActiveModel(model_id="ok", complexity=frozenset({1, 2}))]


def test_llm19_token_limit_deactivation_until_is_three_hours() -> None:
    now = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    until = token_limit_deactivation_until(now=now)
    assert until == now + timedelta(hours=3)


def test_llm20_build_chat_model_returns_routing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    _patch_groq_catalog_for_wiring(monkeypatch)

    settings = load_settings()
    model = build_chat_model(settings)

    assert isinstance(model, RoutingChatModel)
