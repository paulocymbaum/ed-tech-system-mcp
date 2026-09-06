"""Composition root — wire infrastructure adapters and application workflows."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import SecretStr

from mcp_server.application.integration_runtime import (
    configure_lazy_integration_clients,
    register_search_client_builder,
    register_video_client_builder,
)
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
from mcp_server.application.token_counting_runtime import set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    set_workflow_execution_config,
)
from mcp_server.domain.cache import ICacheStore
from mcp_server.domain.external_rate_limit import IExternalRequestRateLimiter
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient
from mcp_server.domain.llm_routing import LLMComplexity
from mcp_server.infrastructure.cache_config import build_cache_rule_set
from mcp_server.infrastructure.cached_adapters import (
    CachedSearchClient,
    CachedVideoSearchClient,
)
from mcp_server.infrastructure.cached_llm import CachedChatModel
from mcp_server.infrastructure.external_rate_limiter import SlidingWindowExternalRequestRateLimiter
from mcp_server.infrastructure.groq_active_model_list_client import (
    CachingGroqActiveModelListClient,
    SupabaseGroqActiveModelListClient,
)
from mcp_server.infrastructure.groq_adapter import build_groq_chat_model
from mcp_server.infrastructure.groq_model_registry import GroqModelRegistry
from mcp_server.infrastructure.llm_debounce import IntervalLLMDebounceGate
from mcp_server.infrastructure.mcp_tool_cache import McpToolInteractionCache
from mcp_server.infrastructure.rate_limited_adapters import (
    RateLimitedSearchClient,
    RateLimitedVideoSearchClient,
)
from mcp_server.infrastructure.redis_cache_store import NoOpCacheStore, RedisCacheStore
from mcp_server.infrastructure.tavily_search_client import TavilySearchClient
from mcp_server.infrastructure.youtube_client import YouTubeDataApiClient
from mcp_server.operational_config import OperationalConfig

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from mcp_server.settings import Settings

_CACHE_STORE_REQUIRED_MSG = (
    "cache store is required when CACHE_ENABLED=true; "
    "pass the shared store from initialize_application_runtime()"
)
_runtime_cache_store: ICacheStore | None = None

_wired_llm_router: LLMRouter | None = None
_wired_external_rate_limiter: IExternalRequestRateLimiter | None = None

_PRODUCTION_LIKE_APP_ENVS = frozenset({"staging", "production"})
_LOCAL_REDIS_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class ApplicationContext:
    """Wired application runtime created once per process boot."""

    workflow_execution_config: WorkflowExecutionConfig
    cache_store: ICacheStore
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


def production_cache_misconfigured_message(settings: Settings) -> str | None:
    """Return a warning when staging/production lacks Redis cache for LLM/integration I/O."""
    env = settings.app_env.strip().lower()
    if env not in _PRODUCTION_LIKE_APP_ENVS:
        return None
    explicit_url = bool(settings.redis_url and settings.redis_url.strip())
    remote_host = settings.redis_host.strip().lower() not in _LOCAL_REDIS_HOSTS
    redis_configured = explicit_url or remote_host
    if not settings.cache_enabled:
        return (
            f"APP_ENV={settings.app_env} requires CACHE_ENABLED=true and REDIS_URL for LLM, "
            "YouTube, web search, and MCP tool cache. Continuing without cache."
        )
    if not redis_configured:
        return (
            f"CACHE_ENABLED=true in APP_ENV={settings.app_env} but REDIS_URL is unset "
            "(localhost Redis fallback is not a production endpoint). "
            "Set REDIS_URL to the managed Redis URL. Continuing."
        )
    return None


def warn_if_production_cache_misconfigured(settings: Settings) -> None:
    """Log when staging/production is missing the required Redis cache configuration."""
    message = production_cache_misconfigured_message(settings)
    if message is not None:
        logging.getLogger(__name__).warning(message)


def create_cache_store(settings: Settings) -> ICacheStore:
    """Return Redis store when caching is enabled; otherwise a no-op store."""
    if not settings.cache_enabled:
        return NoOpCacheStore()
    redis_url = resolve_redis_url(settings)
    if redis_url is None:
        return NoOpCacheStore()
    return RedisCacheStore(redis_url)


def build_external_rate_limiter(settings: Settings) -> IExternalRequestRateLimiter:
    """Return the shared per-minute outbound API rate limiter."""
    global _wired_external_rate_limiter
    if _wired_external_rate_limiter is None:
        _wired_external_rate_limiter = SlidingWindowExternalRequestRateLimiter(
            settings.external_request_limit_per_minute,
        )
    return _wired_external_rate_limiter


def build_search_client(
    settings: Settings,
    cache: ICacheStore | None = None,
    rate_limiter: IExternalRequestRateLimiter | None = None,
) -> ISearchClient:
    """Build the web search client. Tavily is required (no DuckDuckGo fallback)."""
    api_key = (
        settings.tavily_api_key.get_secret_value().strip()
        if settings.tavily_api_key is not None
        else ""
    )
    if not api_key:
        msg = "TAVILY_API_KEY is required to build the web search client"
        raise ValueError(msg)
    client: ISearchClient = TavilySearchClient(api_key)
    limiter = rate_limiter or build_external_rate_limiter(settings)
    client = RateLimitedSearchClient(client, limiter)
    if not settings.cache_enabled or cache is None:
        return client
    return CachedSearchClient(client, cache, build_cache_rule_set(settings))


def build_video_client(
    settings: Settings,
    cache: ICacheStore | None = None,
    rate_limiter: IExternalRequestRateLimiter | None = None,
) -> IVideoSearchClient:
    """Build the video search client, optionally wrapped with cache-aside."""
    api_key = settings.youtube_api_key.get_secret_value() if settings.youtube_api_key else ""
    client: IVideoSearchClient = YouTubeDataApiClient(api_key)
    limiter = rate_limiter or build_external_rate_limiter(settings)
    client = RateLimitedVideoSearchClient(client, limiter)
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
        validation_retries=operational.validation_retries,
    )


def build_llm_router(settings: Settings) -> LLMRouter:
    """Build the Groq LLM router with Supabase active-model registry and debounce gate."""
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

    list_client = CachingGroqActiveModelListClient(
        SupabaseGroqActiveModelListClient(
            settings.supabase_url,
            settings.supabase_service_role_key,
        ),
        ttl_seconds=settings.groq_active_model_list_cache_seconds,
    )
    registry = GroqModelRegistry(list_client)
    debounce_gate = IntervalLLMDebounceGate(settings.llm_router_debounce_seconds)
    rate_limiter = build_external_rate_limiter(settings)
    router = LLMRouter(
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        registry=registry,
        debounce_gate=debounce_gate,
        model_builder=_build_groq_model,
        default_complexity=LLMComplexity(settings.llm_complexity),
        external_rate_limiter=rate_limiter,
        max_fallbacks=settings.llm_router_max_fallbacks,
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
        model_name="routing-groq",
    )


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
    global _runtime_cache_store
    config = build_workflow_execution_config(operational)
    set_workflow_execution_config(config)
    if settings is None:
        cache_store: ICacheStore = NoOpCacheStore()
        configure_lazy_chat_model(None)
        configure_lazy_integration_clients(None)
        set_mcp_tool_cache(None)
        from mcp_server.application.inbound_rate_limit_runtime import (
            InboundRateLimitRuntime,
            set_inbound_rate_limit_runtime,
        )

        set_inbound_rate_limit_runtime(InboundRateLimitRuntime(enabled=False, limiter=None))
        from mcp_server.application.agents.socratic.nodes import (
            register_tutor_session_draft,
        )

        register_tutor_session_draft(None)
        _runtime_cache_store = cache_store
        return ApplicationContext(
            workflow_execution_config=config,
            cache_store=cache_store,
            mcp_tool_cache=None,
        )

    from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter

    settings.assert_inbound_token_if_required()
    warn_if_production_cache_misconfigured(settings)

    set_token_counter(TiktokenTokenCounter())
    cache_store = create_cache_store(settings)
    configure_lazy_chat_model(settings, cache_store)
    configure_lazy_integration_clients(settings, cache_store)
    tool_cache = build_mcp_tool_cache(settings, cache_store)
    set_mcp_tool_cache(tool_cache)

    from mcp_server.application.agents.project_review.nodes import (
        register_project_review_error_reporter,
        register_project_review_repository,
    )
    from mcp_server.infrastructure.ai_generation_job_progress import (
        SupabaseAiGenerationJobProgress,
    )
    from mcp_server.infrastructure.groq_model_error_reporter import (
        GroqModelErrorReporter,
    )
    from mcp_server.infrastructure.project_review_repository import ProjectReviewRepository
    from mcp_server.interface.custom_tools_project_review import (
        register_project_review_tool_repository,
    )

    job_progress = SupabaseAiGenerationJobProgress(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    project_review_repo = ProjectReviewRepository(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    register_project_review_repository(project_review_repo)
    register_project_review_tool_repository(
        project_review_repo,
        job_progress=job_progress,
    )
    register_project_review_error_reporter(
        GroqModelErrorReporter(settings.supabase_url, settings.supabase_service_role_key)
    )

    from mcp_server.application.agents.socratic.nodes import (
        register_socratic_catalog,
        register_tutor_session_draft,
    )
    from mcp_server.infrastructure.socratic_catalog_repository import SocraticCatalogRepository
    from mcp_server.infrastructure.tutor_session_draft import SupabaseTutorSessionDraft

    register_socratic_catalog(
        SocraticCatalogRepository(settings.supabase_url, settings.supabase_service_role_key)
    )
    register_tutor_session_draft(
        SupabaseTutorSessionDraft(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    )

    from mcp_server.infrastructure.authoring_backend_client import AuthoringBackendClientFactory
    from mcp_server.infrastructure.graph_search_repository import GraphSearchRepository
    from mcp_server.interface.custom_tools_authoring import register_authoring_tools

    anon = (
        settings.supabase_anon_key.get_secret_value()
        if settings.supabase_anon_key is not None
        else None
    )
    register_authoring_tools(
        graph_search=GraphSearchRepository(
            settings.supabase_url,
            settings.supabase_service_role_key,
        ),
        backend_factory=AuthoringBackendClientFactory(
            settings.supabase_url,
            anon_key=anon,
        ),
        job_progress=job_progress,
    )

    from mcp_server.application.mcp_tool_auth_runtime import (
        McpToolAuthRuntime,
        set_mcp_tool_auth_runtime,
    )
    from mcp_server.infrastructure.caller_identity_adapter import SupabaseCallerIdentityAdapter
    from mcp_server.interface.mcp_server import mcp

    inbound = settings.inbound_token_value()
    if inbound:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

        mcp.auth = StaticTokenVerifier(
            tokens={inbound: {"client_id": "ed-tech-bff", "scopes": ["mcp"]}},
            required_scopes=["mcp"],
        )
    else:
        mcp.auth = None
    identity = None
    if settings.mcp_require_caller_jwt:
        identity = SupabaseCallerIdentityAdapter(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    set_mcp_tool_auth_runtime(
        McpToolAuthRuntime(
            require_caller_jwt=settings.mcp_require_caller_jwt,
            identity=identity,
        )
    )
    from mcp_server.application.inbound_rate_limit_runtime import (
        InboundRateLimitRuntime,
        set_inbound_rate_limit_runtime,
    )
    from mcp_server.infrastructure.inbound_rate_limiter import (
        KeyedSlidingWindowInboundRateLimiter,
    )

    http_like = settings.mcp_transport in {"http", "sse", "streamable-http"}
    set_inbound_rate_limit_runtime(
        InboundRateLimitRuntime(
            enabled=http_like,
            limiter=KeyedSlidingWindowInboundRateLimiter(
                settings.mcp_inbound_limit_per_minute,
            )
            if http_like
            else None,
        )
    )

    _runtime_cache_store = cache_store
    return ApplicationContext(
        workflow_execution_config=config,
        cache_store=cache_store,
        mcp_tool_cache=tool_cache,
    )


def _lazy_build_chat_model(
    settings: LLMSettings,
    cache: ICacheStore | None,
) -> BaseChatModel:
    return build_chat_model(settings, cache)  # type: ignore[arg-type]


def _lazy_build_search_client(
    settings: Settings,
    cache: ICacheStore | None,
) -> ISearchClient:
    return build_search_client(settings, cache)  # type: ignore[arg-type]


def _lazy_build_video_client(
    settings: Settings,
    cache: ICacheStore | None,
) -> IVideoSearchClient:
    return build_video_client(settings, cache)  # type: ignore[arg-type]


register_chat_model_builder(_lazy_build_chat_model)
register_search_client_builder(_lazy_build_search_client)
register_video_client_builder(_lazy_build_video_client)


def shutdown_application_runtime_sync() -> None:
    """Close Redis (if wired). Safe from atexit when no event loop is running."""
    store = _runtime_cache_store
    closer = getattr(store, "close", None)
    if closer is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(closer())
        return
    loop.create_task(closer())

