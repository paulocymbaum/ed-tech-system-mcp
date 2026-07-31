"""Cache layer contract tests."""

from __future__ import annotations

import asyncio
import json

import pytest

from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRule,
    CacheRuleSet,
    ICacheStore,
    build_cache_key,
)
from mcp_server.domain.interfaces import IDataRepository, ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.infrastructure.cache_config import build_cache_rule_set
from mcp_server.infrastructure.cache_envelope import McpToolCacheEnvelope
from mcp_server.infrastructure.cache_observability import get_cache_metrics, reset_cache_metrics
from mcp_server.infrastructure.cache_serialization import (
    DOCUMENT_CONTENT_MAX_LEN,
    deserialize_documents,
    serialize_documents,
    serialize_snippets,
)
from mcp_server.infrastructure.cached_adapters import (
    CachedDataRepository,
    CachedSearchClient,
    CachedVideoSearchClient,
)
from mcp_server.infrastructure.mcp_tool_cache import McpToolInteractionCache
from mcp_server.infrastructure.redis_cache_store import NoOpCacheStore, RedisCacheStore
from mcp_server.settings import load_settings
from mcp_server.wiring import (
    ApplicationContext,
    build_data_repository,
    build_document_video_workflow,
    build_mcp_tool_cache,
    create_cache_store,
    initialize_application_runtime,
    resolve_redis_url,
)


class InMemoryCacheStore(ICacheStore):
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.get_calls = 0
        self.set_calls = 0

    async def get(self, key: str) -> bytes | None:
        self.get_calls += 1
        return self.storage.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self.set_calls += 1
        self.storage[key] = value
        self.ttls[key] = ttl_seconds


class CountingRepository(IDataRepository):
    def __init__(self, documents: list[DocumentHit]) -> None:
        self._documents = documents
        self.calls = 0

    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        self.calls += 1
        return self._documents


class SlowCountingRepository(IDataRepository):
    def __init__(self, documents: list[DocumentHit], *, delay_seconds: float = 0.05) -> None:
        self._documents = documents
        self._delay_seconds = delay_seconds
        self.calls = 0

    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        self.calls += 1
        await asyncio.sleep(self._delay_seconds)
        return self._documents


class CountingSearchClient(ISearchClient):
    def __init__(self, snippets: list[str]) -> None:
        self._snippets = snippets
        self.calls = 0

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        self.calls += 1
        return self._snippets


class SlowCountingSearchClient(ISearchClient):
    def __init__(self, snippets: list[str], *, delay_seconds: float = 0.05) -> None:
        self._snippets = snippets
        self._delay_seconds = delay_seconds
        self.calls = 0

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        self.calls += 1
        await asyncio.sleep(self._delay_seconds)
        return self._snippets


class CountingVideoClient(IVideoSearchClient):
    def __init__(self, videos: list[VideoResult]) -> None:
        self._videos = videos
        self.calls = 0

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        self.calls += 1
        return self._videos


class SlowCountingVideoClient(IVideoSearchClient):
    def __init__(self, videos: list[VideoResult], *, delay_seconds: float = 0.05) -> None:
        self._videos = videos
        self._delay_seconds = delay_seconds
        self.calls = 0

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        self.calls += 1
        await asyncio.sleep(self._delay_seconds)
        return self._videos


def test_c01_build_cache_key_is_deterministic() -> None:
    params = {"query": "plants", "limit": 10, "safe_search": True}
    first = build_cache_key(CacheOperationType.SUPABASE_FIND_DOCUMENTS, params, prefix="supabase")
    second = build_cache_key(CacheOperationType.SUPABASE_FIND_DOCUMENTS, params, prefix="supabase")
    assert first == second
    assert first.startswith("supabase:")


def test_c02_build_cache_key_normalizes_dict_key_order() -> None:
    first = build_cache_key(
        CacheOperationType.WEB_SEARCH,
        {"max_results": 5, "query": "math"},
        prefix="web",
    )
    second = build_cache_key(
        CacheOperationType.WEB_SEARCH,
        {"query": "math", "max_results": 5},
        prefix="web",
    )
    assert first == second


def test_c12_cache_rule_set_is_enabled() -> None:
    enabled_rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=True,
            )
        }
    )
    disabled_rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=False,
            )
        }
    )
    empty_rules = CacheRuleSet()

    assert enabled_rules.is_enabled(CacheOperationType.WEB_SEARCH) is True
    assert disabled_rules.is_enabled(CacheOperationType.WEB_SEARCH) is False
    assert empty_rules.is_enabled(CacheOperationType.WEB_SEARCH) is False


async def test_c03_cached_repository_hits_cache_on_second_call() -> None:
    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=True,
                ttl_seconds=120,
                key_prefix="supabase",
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    first = await repository.find_documents("plants", limit=5)
    second = await repository.find_documents("plants", limit=5)

    assert first == second == [doc]
    assert inner.calls == 1
    assert cache.set_calls == 1
    assert cache.get_calls == 3


async def test_c04_cached_repository_bypasses_cache_when_rule_disabled() -> None:
    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=False,
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    await repository.find_documents("plants")
    await repository.find_documents("plants")

    assert inner.calls == 2
    assert cache.set_calls == 0


async def test_c05_cached_video_client_respects_language_and_safe_search() -> None:
    video = VideoResult(title="V", channel="C", url="https://example.com")
    inner = CountingVideoClient([video])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.YOUTUBE_SEARCH_VIDEOS: CacheRule(
                operation=CacheOperationType.YOUTUBE_SEARCH_VIDEOS,
                enabled=True,
                ttl_seconds=60,
                key_prefix="youtube",
            )
        }
    )
    client = CachedVideoSearchClient(inner, cache, rules)

    await client.search_videos("math", max_results=3, language="pt", safe_search=False)
    await client.search_videos("math", max_results=3, language="pt", safe_search=False)

    assert inner.calls == 1


async def test_c13_cached_search_client_hits_cache_on_second_call() -> None:
    snippets = ["result one", "result two"]
    inner = CountingSearchClient(snippets)
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=True,
                ttl_seconds=300,
                key_prefix="web",
            )
        }
    )
    client = CachedSearchClient(inner, cache, rules)

    first = await client.search("algebra", max_results=5)
    second = await client.search("algebra", max_results=5)

    assert first == second == snippets
    assert inner.calls == 1
    assert cache.set_calls == 1


async def test_c14_cached_search_client_misses_on_different_max_results() -> None:
    snippets = ["result"]
    inner = CountingSearchClient(snippets)
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=True,
                ttl_seconds=300,
                key_prefix="web",
            )
        }
    )
    client = CachedSearchClient(inner, cache, rules)

    await client.search("algebra", max_results=5)
    await client.search("algebra", max_results=10)

    assert inner.calls == 2


async def test_c15_mcp_tool_cache_returns_cached_result_without_reinvoking() -> None:
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
    tool_cache = McpToolInteractionCache(cache, rules)
    invocations = 0

    async def invoker() -> dict[str, str]:
        nonlocal invocations
        invocations += 1
        return {"status": "ok"}

    first = await tool_cache.get_or_invoke("health_check", {}, invoker)
    second = await tool_cache.get_or_invoke("health_check", {}, invoker)

    assert first == second == {"status": "ok"}
    assert invocations == 1
    assert cache.set_calls == 1


async def test_c16_mcp_tool_cache_bypasses_when_rule_disabled() -> None:
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.MCP_TOOL: CacheRule(
                operation=CacheOperationType.MCP_TOOL,
                enabled=False,
            )
        }
    )
    tool_cache = McpToolInteractionCache(cache, rules)
    invocations = 0

    async def invoker() -> str:
        nonlocal invocations
        invocations += 1
        return "live"

    await tool_cache.get_or_invoke("health_check", {}, invoker)
    await tool_cache.get_or_invoke("health_check", {}, invoker)

    assert invocations == 2
    assert cache.set_calls == 0


async def test_c17_noop_cache_store_always_misses() -> None:
    store = NoOpCacheStore()
    await store.set("key", b"value", ttl_seconds=60)
    assert await store.get("key") is None


async def test_c18_redis_cache_store_degrades_on_unreachable_host() -> None:
    store = RedisCacheStore("redis://127.0.0.1:1")
    assert await store.get("missing-key") is None


def test_c06_settings_loads_redis_and_cache_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CACHE_TTL_WEB_SEARCH", "900")
    monkeypatch.setenv("CACHE_KEY_PREFIX_WEB", "custom-web")

    settings = load_settings()

    assert settings.cache_enabled is True
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.cache_ttl_web_search == 900
    assert settings.cache_key_prefix_web == "custom-web"


def test_c07_resolve_redis_url_from_host_and_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "cache.local")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")

    settings = load_settings()
    assert resolve_redis_url(settings) == "redis://:secret@cache.local:6380/0"


def test_c08_create_cache_store_returns_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    settings = load_settings()
    assert type(create_cache_store(settings)).__name__ == "NoOpCacheStore"


def test_c09_build_cache_rule_set_applies_ttl_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "true")
    monkeypatch.setenv("CACHE_TTL_SUPABASE_FIND_DOCUMENTS", "42")

    settings = load_settings()
    rules = build_cache_rule_set(settings)
    rule = rules.for_operation(CacheOperationType.SUPABASE_FIND_DOCUMENTS)

    assert rule is not None
    assert rule.enabled is True
    assert rule.ttl_seconds == 42


def test_c10_build_document_video_workflow_returns_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    settings = load_settings()
    workflow = build_document_video_workflow(settings)

    assert workflow is not None


def test_c11_build_data_repository_without_cache_is_uncached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    settings = load_settings()
    repository = build_data_repository(settings, create_cache_store(settings))

    assert type(repository).__name__ == "RateLimitedDataRepository"


def test_c19_build_mcp_tool_cache_returns_helper_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    settings = load_settings()
    assert isinstance(build_mcp_tool_cache(settings), McpToolInteractionCache)


def test_c20_llm_completion_default_cache_rule() -> None:
    from mcp_server.domain.cache import DEFAULT_CACHE_RULES

    rule = DEFAULT_CACHE_RULES[CacheOperationType.LLM_COMPLETION]
    assert rule.ttl_seconds == 3600
    assert rule.key_prefix == "llm"


def test_c21_initialize_application_runtime_creates_single_cache_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_server.operational_config import OperationalConfig

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("CACHE_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    operational = OperationalConfig(
        node_retries=1,
        workflow_timeout=60,
        agent_node_timeout=30,
    )
    settings = load_settings()
    create_calls = 0
    original_create = create_cache_store

    def _counting_create(settings_arg: object) -> ICacheStore:
        nonlocal create_calls
        create_calls += 1
        return original_create(settings_arg)  # type: ignore[arg-type]

    monkeypatch.setattr("mcp_server.wiring.create_cache_store", _counting_create)
    context = initialize_application_runtime(operational, settings)

    assert isinstance(context, ApplicationContext)
    assert create_calls == 1
    assert context.document_video_workflow is None
    assert context.mcp_tool_cache is not None


def test_c22_mcp_tool_cache_envelope_round_trips_complex_result() -> None:
    video = VideoResult(
        title="Intro to Algebra",
        channel="EduChannel",
        url="https://example.com/video",
        duration_seconds=600,
        relevance_score=0.95,
    )
    payload = McpToolCacheEnvelope.pack([video])
    restored = McpToolCacheEnvelope.unpack(payload)
    assert restored == [video.model_dump(mode="json")]


async def test_c23_cached_repository_logs_hit_on_second_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    reset_cache_metrics()
    caplog.set_level(logging.DEBUG, logger="mcp_server.infrastructure.cache_observability")

    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=True,
                ttl_seconds=120,
                key_prefix="supabase",
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    await repository.find_documents("plants", limit=5)
    await repository.find_documents("plants", limit=5)

    assert "cache hit" in caplog.text
    assert get_cache_metrics().hits == 1
    assert get_cache_metrics().misses == 1


async def test_c24_cached_llm_logs_hit_on_second_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    from mcp_server.infrastructure.cached_llm import CachedChatModel

    reset_cache_metrics()
    caplog.set_level(logging.DEBUG, logger="mcp_server.infrastructure.cache_observability")

    class _CountingChatModel:
        calls = 0

        async def _agenerate(self, messages: object, **kwargs: object) -> ChatResult:
            _CountingChatModel.calls += 1
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="cached-response"))]
            )

    inner = _CountingChatModel()
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
    model = CachedChatModel(inner, cache, rules, model_name="llama-3.3-70b-versatile")  # type: ignore[arg-type]

    await model._agenerate([])
    await model._agenerate([])

    assert _CountingChatModel.calls == 1
    assert "cache hit" in caplog.text
    assert get_cache_metrics().hits == 1
    assert get_cache_metrics().misses == 1


async def test_c25_port_call_span_logs_disabled_on_cache_bypass(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.infrastructure.port_observability")

    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=False,
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    await repository.find_documents("plants", limit=5)

    assert "port call operation=supabase.find_documents" in caplog.text
    assert "cache=disabled" in caplog.text
    assert "duration_ms=" in caplog.text


async def test_c26_port_call_span_logs_miss_then_hit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.infrastructure.port_observability")

    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=True,
                ttl_seconds=120,
                key_prefix="supabase",
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    await repository.find_documents("plants", limit=5)
    await repository.find_documents("plants", limit=5)

    assert caplog.text.count("port call operation=supabase.find_documents") == 2
    assert "cache=miss" in caplog.text
    assert "cache=hit" in caplog.text


async def test_c27_port_call_span_logs_miss_then_hit_for_web_search(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.infrastructure.port_observability")

    snippets = ["result one", "result two"]
    inner = CountingSearchClient(snippets)
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=True,
                ttl_seconds=300,
                key_prefix="web",
            )
        }
    )
    client = CachedSearchClient(inner, cache, rules)

    await client.search("algebra", max_results=5)
    await client.search("algebra", max_results=5)

    assert caplog.text.count("port call operation=web.search") == 2
    assert "cache=miss" in caplog.text
    assert "cache=hit" in caplog.text


async def test_c28_port_call_span_logs_miss_then_hit_for_youtube_search_videos(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="mcp_server.infrastructure.port_observability")

    video = VideoResult(title="V", channel="C", url="https://example.com")
    inner = CountingVideoClient([video])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.YOUTUBE_SEARCH_VIDEOS: CacheRule(
                operation=CacheOperationType.YOUTUBE_SEARCH_VIDEOS,
                enabled=True,
                ttl_seconds=60,
                key_prefix="youtube",
            )
        }
    )
    client = CachedVideoSearchClient(inner, cache, rules)

    await client.search_videos("math", max_results=3, language="pt", safe_search=False)
    await client.search_videos("math", max_results=3, language="pt", safe_search=False)

    assert caplog.text.count("port call operation=youtube.search_videos") == 2
    assert "cache=miss" in caplog.text
    assert "cache=hit" in caplog.text


def test_c29_document_cache_prunes_content_and_metadata() -> None:
    long_content = "x" * (DOCUMENT_CONTENT_MAX_LEN + 50)
    doc = DocumentHit(
        id="1",
        title="Title",
        content=long_content,
        metadata={"source": "supabase", "chunk": "99"},
    )

    payload = serialize_documents([doc])
    restored = deserialize_documents(payload)

    assert len(restored) == 1
    assert restored[0].id == "1"
    assert restored[0].title == "Title"
    assert restored[0].content == f"{long_content[:DOCUMENT_CONTENT_MAX_LEN]}..."
    assert restored[0].metadata == {}
    assert payload.startswith(b"\x02")


def test_c30_large_snippet_list_uses_gzip_envelope() -> None:
    snippets = ["snippet-" + ("y" * 200) for _ in range(20)]
    payload = serialize_snippets(snippets)

    assert payload.startswith(b"\x02z")


async def test_c31_oversize_payload_skips_set_but_returns_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mcp_server.infrastructure.cache_serialization.MAX_CACHE_PAYLOAD_BYTES",
        32,
    )
    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = CountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=True,
                ttl_seconds=120,
                key_prefix="supabase",
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    result = await repository.find_documents("plants", limit=5)

    assert result == [doc]
    assert inner.calls == 1
    assert cache.set_calls == 0
    assert cache.storage == {}


async def test_c32_parallel_misses_invoke_inner_port_once() -> None:
    doc = DocumentHit(id="1", title="Title", content="Body")
    inner = SlowCountingRepository([doc])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
                operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
                enabled=True,
                ttl_seconds=120,
                key_prefix="supabase",
            )
        }
    )
    repository = CachedDataRepository(inner, cache, rules)

    await asyncio.gather(*[repository.find_documents("plants", limit=5) for _ in range(8)])

    assert inner.calls == 1
    assert cache.set_calls == 1


async def test_c34_cached_search_client_parallel_misses_invoke_inner_once() -> None:
    snippets = ["result one", "result two"]
    inner = SlowCountingSearchClient(snippets)
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.WEB_SEARCH: CacheRule(
                operation=CacheOperationType.WEB_SEARCH,
                enabled=True,
                ttl_seconds=300,
                key_prefix="web",
            )
        }
    )
    client = CachedSearchClient(inner, cache, rules)

    await asyncio.gather(*[client.search("algebra", max_results=5) for _ in range(8)])

    assert inner.calls == 1
    assert cache.set_calls == 1


async def test_c35_cached_video_client_parallel_misses_invoke_inner_once() -> None:
    video = VideoResult(title="V", channel="C", url="https://example.com")
    inner = SlowCountingVideoClient([video])
    cache = InMemoryCacheStore()
    rules = CacheRuleSet(
        rules={
            CacheOperationType.YOUTUBE_SEARCH_VIDEOS: CacheRule(
                operation=CacheOperationType.YOUTUBE_SEARCH_VIDEOS,
                enabled=True,
                ttl_seconds=60,
                key_prefix="youtube",
            )
        }
    )
    client = CachedVideoSearchClient(inner, cache, rules)

    await asyncio.gather(
        *[
            client.search_videos("math", max_results=3, language="pt", safe_search=False)
            for _ in range(8)
        ]
    )

    assert inner.calls == 1
    assert cache.set_calls == 1


def test_c33_legacy_unprefixed_document_payload_deserializes() -> None:
    legacy = json.dumps([{"id": "1", "title": "Title", "content": "Body"}]).encode("utf-8")
    restored = deserialize_documents(legacy)

    assert restored == [DocumentHit(id="1", title="Title", content="Body")]


async def test_c36_mcp_tool_cache_parallel_misses_invoke_once() -> None:
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
    tool_cache = McpToolInteractionCache(cache, rules)
    invocations = 0

    async def slow_invoker() -> dict[str, str]:
        nonlocal invocations
        invocations += 1
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    await asyncio.gather(
        *[tool_cache.get_or_invoke("health_check", {}, slow_invoker) for _ in range(8)]
    )

    assert invocations == 1
    assert cache.set_calls == 1


async def test_c37_mcp_tool_cache_skips_oversize_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mcp_server.infrastructure.cache_serialization.MAX_CACHE_PAYLOAD_BYTES",
        32,
    )
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
    tool_cache = McpToolInteractionCache(cache, rules)
    large_result = {"data": "x" * 10_000}

    async def invoker() -> dict[str, str]:
        return large_result

    result = await tool_cache.get_or_invoke("find_documents", {"query": "big"}, invoker)

    assert result == large_result
    assert cache.set_calls == 0
    assert cache.storage == {}


def test_c38_cache_hit_rate_logged_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from mcp_server.infrastructure.cache_observability import record_cache_hit, record_cache_miss

    reset_cache_metrics()
    caplog.set_level(logging.INFO, logger="mcp_server.infrastructure.cache_observability")

    for _ in range(9):
        record_cache_miss("mcp_tool", "key")
    record_cache_hit("mcp_tool", "key")

    assert "cache hit-rate operation=mcp_tool" in caplog.text
    assert "hit_rate=" in caplog.text
