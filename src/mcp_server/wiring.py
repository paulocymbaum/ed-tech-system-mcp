"""Composition root — wire infrastructure adapters and application workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import SecretStr

from mcp_server.application.llm import (
    LLMSettings,
    configure_lazy_chat_model,
    create_chat_model,
    register_chat_model_builder,
    register_groq_model_builder,
    register_llm_router,
)
from mcp_server.application.llm_models import register_groq_language_models
from mcp_server.application.llm_router import LLMRouter
from mcp_server.application.mcp_tool_cache_runtime import set_mcp_tool_cache
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    set_workflow_execution_config,
)
from mcp_server.application.workflow_runtime import (
    WorkflowSettings,
    configure_lazy_document_video_workflow,
    register_document_video_workflow_builder,
)
from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.cache import ICacheStore
from mcp_server.domain.interfaces import IDataRepository, ISearchClient, IVideoSearchClient
from mcp_server.domain.llm_routing import LLMComplexity
from mcp_server.infrastructure.cache_config import build_cache_rule_set
from mcp_server.infrastructure.cached_adapters import (
    CachedDataRepository,
    CachedSearchClient,
    CachedVideoSearchClient,
)
from mcp_server.infrastructure.cached_llm import CachedChatModel
from mcp_server.infrastructure.groq_adapter import build_groq_chat_model
from mcp_server.infrastructure.groq_model_catalog import (
    CachingGroqModelCatalogClient,
    GroqModelCatalogClient,
)
from mcp_server.infrastructure.groq_model_catalog_cache import FileGroqModelCatalogCache
from mcp_server.infrastructure.groq_model_registry import GroqModelRegistry
from mcp_server.infrastructure.llm_debounce import IntervalLLMDebounceGate
from mcp_server.infrastructure.mcp_tool_cache import McpToolInteractionCache
from mcp_server.infrastructure.redis_cache_store import NoOpCacheStore, RedisCacheStore
from mcp_server.infrastructure.search_client import DuckDuckGoSearchClient
from mcp_server.infrastructure.supabase_client import SupabaseRepository
from mcp_server.infrastructure.youtube_client import YouTubeDataApiClient
from mcp_server.operational_config import OperationalConfig

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from mcp_server.settings import Settings

_CACHE_STORE_REQUIRED_MSG = (
    "cache store is required when CACHE_ENABLED=true; "
    "pass the shared store from initialize_application_runtime()"
)

_wired_llm_router: LLMRouter | None = None


@dataclass(frozen=True)
class ApplicationContext:
    """Wired application runtime created once per process boot."""

    workflow_execution_config: WorkflowExecutionConfig
    cache_store: ICacheStore
    document_video_workflow: DocumentVideoWorkflow | None
    mcp_tool_cache: McpToolInteractionCache | None


def resolve_redis_url(settings: Settings) -> str | None:
    """Build a Redis URL from settings, preferring REDIS_URL when set."""
    if settings.redis_url:
        return settings.redis_url
    password = (
        settings.redis_password.get_secret_value() if settings.redis_password is not None else None
    )
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{settings.redis_host}:{settings.redis_port}/0"


def create_cache_store(settings: Settings) -> ICacheStore:
    """Return Redis store when caching is enabled; otherwise a no-op store."""
    if not settings.cache_enabled:
        return NoOpCacheStore()
    redis_url = resolve_redis_url(settings)
    if redis_url is None:
        return NoOpCacheStore()
    return RedisCacheStore(redis_url)


def build_data_repository(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> IDataRepository:
    """Build the document repository, optionally wrapped with cache-aside."""
    repository: IDataRepository = SupabaseRepository(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )
    if not settings.cache_enabled or cache is None:
        return repository
    return CachedDataRepository(repository, cache, build_cache_rule_set(settings))


def build_search_client(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> ISearchClient:
    """Build the web search client, optionally wrapped with cache-aside.

    # deferred — web search: factory only; inject via ``langchain_tools.search_web``
    when BL-022 adapter implementation and MCP ``search_web`` tool ship (see
    AGENTIC_ARCHITECTURE.md § Web search wiring).
    """
    client: ISearchClient = DuckDuckGoSearchClient()
    if not settings.cache_enabled or cache is None:
        return client
    return CachedSearchClient(client, cache, build_cache_rule_set(settings))


def build_video_client(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> IVideoSearchClient:
    """Build the video search client, optionally wrapped with cache-aside."""
    api_key = settings.youtube_api_key.get_secret_value() if settings.youtube_api_key else ""
    client: IVideoSearchClient = YouTubeDataApiClient(api_key)
    if not settings.cache_enabled or cache is None:
        return client
    return CachedVideoSearchClient(client, cache, build_cache_rule_set(settings))


def build_workflow_execution_config(
    operational: OperationalConfig,
) -> WorkflowExecutionConfig:
    """Map entrypoint operational settings to application runtime config."""
    return WorkflowExecutionConfig(
        node_retries=operational.node_retries,
        workflow_timeout_seconds=operational.workflow_timeout,
        agent_node_timeout_seconds=operational.agent_node_timeout,
    )


def build_llm_router(settings: Settings) -> LLMRouter:
    """Build the Groq LLM router with catalog-backed registry and debounce gate."""
    global _wired_llm_router
    if _wired_llm_router is not None:
        register_llm_router(_wired_llm_router)
        return _wired_llm_router

    if settings.groq_api_key is None:
        msg = "GROQ_API_KEY is required to build the LLM router"
        raise ValueError(msg)

    def _build_groq_model(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
        return build_groq_chat_model(
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
        )

    register_groq_model_builder(_build_groq_model)

    catalog_client = CachingGroqModelCatalogClient(
        GroqModelCatalogClient(settings.groq_api_key),
        FileGroqModelCatalogCache(
            settings.groq_model_catalog_cache_path,
            ttl_seconds=settings.groq_model_catalog_ttl_days * 24 * 60 * 60,
        ),
    )
    registry = GroqModelRegistry(catalog_client)
    debounce_gate = IntervalLLMDebounceGate(settings.llm_router_debounce_seconds)
    router = LLMRouter(
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        registry=registry,
        debounce_gate=debounce_gate,
        model_builder=_build_groq_model,
        default_complexity=LLMComplexity(settings.llm_complexity),
    )
    router.refresh_registry()
    register_groq_language_models(registry.list_records())
    register_llm_router(router)
    _wired_llm_router = router
    return router


def reset_wired_llm_router() -> None:
    """Clear the memoized router (for tests)."""
    global _wired_llm_router
    _wired_llm_router = None


def build_chat_model(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> BaseChatModel:
    """Build the application chat model, optionally wrapped with cache-aside.

    When ``CACHE_ENABLED=true``, ``cache`` must be the shared store from
    ``initialize_application_runtime()`` — do not call this builder directly
    with caching enabled.
    """
    build_llm_router(settings)
    model = create_chat_model(settings)
    if not settings.cache_enabled:
        return model

    if cache is None:
        raise ValueError(_CACHE_STORE_REQUIRED_MSG)
    store = cache
    return CachedChatModel(
        model,
        store,
        build_cache_rule_set(settings),
        model_name=settings.llm_model,
    )


def build_document_video_workflow(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> DocumentVideoWorkflow:
    """Wire application workflow with cached adapters when cache is enabled.

    When ``CACHE_ENABLED=true``, ``cache`` must be the shared store from
    ``initialize_application_runtime()`` — do not call this builder directly
    with caching enabled.
    """
    if settings.cache_enabled and cache is None:
        raise ValueError(_CACHE_STORE_REQUIRED_MSG)
    store = cache if cache is not None else create_cache_store(settings)
    repository = build_data_repository(settings, store)
    video_client = build_video_client(settings, store)
    return DocumentVideoWorkflow(repository, video_client)


def build_mcp_tool_cache(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> McpToolInteractionCache:
    """Build MCP tool interaction cache helper.

    When ``CACHE_ENABLED=true``, ``cache`` must be the shared store from
    ``initialize_application_runtime()`` — do not call this builder directly
    with caching enabled.
    """
    if settings.cache_enabled and cache is None:
        raise ValueError(_CACHE_STORE_REQUIRED_MSG)
    store = cache if cache is not None else create_cache_store(settings)
    return McpToolInteractionCache(store, build_cache_rule_set(settings))


def initialize_application_runtime(
    operational: OperationalConfig,
    settings: Settings | None = None,
) -> ApplicationContext:
    """Initialize application-layer runtime config and wired dependencies."""
    config = build_workflow_execution_config(operational)
    set_workflow_execution_config(config)

    if settings is None:
        cache_store: ICacheStore = NoOpCacheStore()
        configure_lazy_chat_model(None)
        configure_lazy_document_video_workflow(None)
        set_mcp_tool_cache(None)
        return ApplicationContext(
            workflow_execution_config=config,
            cache_store=cache_store,
            document_video_workflow=None,
            mcp_tool_cache=None,
        )

    cache_store = create_cache_store(settings)
    configure_lazy_chat_model(settings, cache_store)
    configure_lazy_document_video_workflow(settings, cache_store)
    tool_cache = build_mcp_tool_cache(settings, cache_store)
    set_mcp_tool_cache(tool_cache)
    return ApplicationContext(
        workflow_execution_config=config,
        cache_store=cache_store,
        document_video_workflow=None,
        mcp_tool_cache=tool_cache,
    )


def _lazy_build_chat_model(
    settings: LLMSettings,
    cache: ICacheStore | None,
) -> BaseChatModel:
    return build_chat_model(settings, cache)  # type: ignore[arg-type]


def _lazy_build_document_video_workflow(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> DocumentVideoWorkflow:
    return build_document_video_workflow(settings, cache)  # type: ignore[arg-type]


register_chat_model_builder(_lazy_build_chat_model)
register_document_video_workflow_builder(_lazy_build_document_video_workflow)
