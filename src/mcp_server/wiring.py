"""Composition root — wire infrastructure adapters and application workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp_server.application.llm import (
    LLMSettings,
    configure_lazy_chat_model,
    create_chat_model,
    register_chat_model_builder,
    register_groq_model_builder,
)
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
from mcp_server.infrastructure.cache_config import build_cache_rule_set
from mcp_server.infrastructure.cached_adapters import (
    CachedDataRepository,
    CachedSearchClient,
    CachedVideoSearchClient,
)
from mcp_server.infrastructure.cached_llm import CachedChatModel
from mcp_server.infrastructure.groq_adapter import build_groq_chat_model
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


def build_chat_model(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> BaseChatModel:
    """Build the application chat model, optionally wrapped with cache-aside.

    When ``CACHE_ENABLED=true``, ``cache`` must be the shared store from
    ``initialize_application_runtime()`` — do not call this builder directly
    with caching enabled.
    """
    register_groq_model_builder(
        lambda api_key, model_id, temperature: build_groq_chat_model(
            api_key=api_key,
            model_id=model_id,
            temperature=temperature,
        )
    )
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
