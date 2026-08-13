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
from mcp_server.application.retrieval_runtime import (
    configure_lazy_retrieval_clients,
    register_chunking_strategy_builder,
    register_embedding_provider_builder,
    register_reranker_builder,
    register_vector_index_writer_builder,
    register_vector_retriever_builder,
)
from mcp_server.application.token_counting_runtime import set_token_counter
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
from mcp_server.domain.external_rate_limit import IExternalRequestRateLimiter
from mcp_server.domain.interfaces import (
    IChunkingStrategy,
    IDataRepository,
    IEmbeddingProvider,
    IReranker,
    ISearchClient,
    IVectorIndexWriter,
    IVectorRetriever,
    IVideoSearchClient,
)
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
    RateLimitedDataRepository,
    RateLimitedSearchClient,
    RateLimitedVideoSearchClient,
)
from mcp_server.infrastructure.redis_cache_store import NoOpCacheStore, RedisCacheStore
from mcp_server.infrastructure.retrieval.supabase_vector_index_writer import (
    SupabaseVectorIndexWriter,
)
from mcp_server.infrastructure.retrieval.supabase_vector_retriever import SupabasePgvectorRetriever
from mcp_server.infrastructure.retrieval.vector_store_backend import resolve_vector_store_backend
from mcp_server.infrastructure.search_client import DuckDuckGoSearchClient
from mcp_server.infrastructure.supabase_client import SupabaseRepository
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

_wired_llm_router: LLMRouter | None = None
_wired_external_rate_limiter: IExternalRequestRateLimiter | None = None


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


_BLOCKED_RERANKER_MODELS = frozenset({"jinaai/jina-reranker-v2-base-multilingual"})


def _validate_reranker_model(model: str) -> None:
    if model in _BLOCKED_RERANKER_MODELS:
        msg = f"RERANKER_MODEL '{model}' is blocked for commercial use (NC license)"
        raise ValueError(msg)


def build_embedding_provider(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> IEmbeddingProvider:
    """Build the local embedding provider (ONNX model file cache only — no Redis query vectors)."""
    from mcp_server.infrastructure.embeddings.fastembed_adapter import FastEmbedAdapter

    _ = cache
    return FastEmbedAdapter(
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimension,
        cache_dir=settings.embedding_cache_dir,
    )


def build_vector_retriever(
    settings: Settings,
    cache: ICacheStore | None = None,
) -> IVectorRetriever:
    """Build vector retriever (Chroma fallback or Supabase pgvector)."""
    backend = resolve_vector_store_backend(settings)
    if backend == "chroma":
        from mcp_server.infrastructure.retrieval.chroma_vector_retriever import (
            ChromaVectorRetriever,
        )

        retriever: IVectorRetriever = ChromaVectorRetriever(
            persist_path=settings.chroma_persist_path,
            collection_name=settings.chroma_collection_name,
        )
    else:
        retriever = SupabasePgvectorRetriever(
            settings.supabase_url,
            settings.supabase_service_role_key.get_secret_value(),
        )
    _ = cache
    return retriever


def build_vector_index_writer(settings: Settings) -> IVectorIndexWriter:
    """Build vector index writer (Chroma fallback or Supabase pgvector)."""
    backend = resolve_vector_store_backend(settings)
    if backend == "chroma":
        from mcp_server.infrastructure.retrieval.chroma_vector_index_writer import (
            ChromaVectorIndexWriter,
        )

        return ChromaVectorIndexWriter(
            persist_path=settings.chroma_persist_path,
            collection_name=settings.chroma_collection_name,
        )
    return SupabaseVectorIndexWriter(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )


def build_reranker(settings: Settings) -> IReranker:
    """Build lazy cross-encoder reranker; graph ``rerank_enabled`` gates whether it runs."""
    from mcp_server.infrastructure.rerank.lazy_reranker import LazyFastEmbedReranker

    _validate_reranker_model(settings.reranker_model)
    return LazyFastEmbedReranker(
        model_name=settings.reranker_model,
        cache_dir=settings.embedding_cache_dir,
    )


def build_chunking_strategy(_settings: Settings) -> IChunkingStrategy:
    """Build the document chunking strategy."""
    from mcp_server.infrastructure.chunking.langchain_chunking_adapter import (
        LangChainChunkingAdapter,
    )

    return LangChainChunkingAdapter()


def warm_embedding_provider_on_boot(settings: Settings, cache_store: ICacheStore) -> None:
    """Pre-load the embedding ONNX model when ``EMBEDDING_WARM_ON_BOOT`` is enabled."""
    if not settings.embedding_warm_on_boot:
        return
    provider = build_embedding_provider(settings, cache_store)
    try:
        asyncio.run(provider.embed_queries(["warmup"]))
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Embedding warm-on-boot failed; continuing with lazy load: %s",
            exc,
        )


def build_external_rate_limiter(settings: Settings) -> IExternalRequestRateLimiter:
    """Return the shared per-minute outbound API rate limiter."""
    global _wired_external_rate_limiter
    if _wired_external_rate_limiter is None:
        _wired_external_rate_limiter = SlidingWindowExternalRequestRateLimiter(
            settings.external_request_limit_per_minute,
        )
    return _wired_external_rate_limiter


def build_data_repository(
    settings: Settings,
    cache: ICacheStore | None = None,
    rate_limiter: IExternalRequestRateLimiter | None = None,
) -> IDataRepository:
    """Build the document repository, optionally wrapped with cache-aside."""
    retrieval_mode = settings.retrieval_mode
    if retrieval_mode not in ("vector", "hybrid"):
        retrieval_mode = "hybrid"
    repository: IDataRepository = SupabaseRepository(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
        embedding_provider=build_embedding_provider(settings, cache),
        vector_retriever=build_vector_retriever(settings, cache),
        retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
    )
    limiter = rate_limiter or build_external_rate_limiter(settings)
    _ = cache
    return RateLimitedDataRepository(repository, limiter)


def build_search_client(
    settings: Settings,
    cache: ICacheStore | None = None,
    rate_limiter: IExternalRequestRateLimiter | None = None,
) -> ISearchClient:
    """Build the web search client, preferring Tavily when configured."""
    api_key = (
        settings.tavily_api_key.get_secret_value().strip()
        if settings.tavily_api_key is not None
        else ""
    )
    client: ISearchClient = TavilySearchClient(api_key) if api_key else DuckDuckGoSearchClient()
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
        configure_lazy_integration_clients(None)
        configure_lazy_retrieval_clients(None)
        set_mcp_tool_cache(None)
        return ApplicationContext(
            workflow_execution_config=config,
            cache_store=cache_store,
            document_video_workflow=None,
            mcp_tool_cache=None,
        )

    from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter

    set_token_counter(TiktokenTokenCounter())
    cache_store = create_cache_store(settings)
    configure_lazy_chat_model(settings, cache_store)
    configure_lazy_document_video_workflow(settings, cache_store)
    configure_lazy_integration_clients(settings, cache_store)
    configure_lazy_retrieval_clients(settings, cache_store)
    warm_embedding_provider_on_boot(settings, cache_store)
    tool_cache = build_mcp_tool_cache(settings, cache_store)
    set_mcp_tool_cache(tool_cache)

    from mcp_server.application.agents.project_review.nodes import (
        register_project_review_repository,
    )
    from mcp_server.infrastructure.groq_model_error_reporter import (
        GroqModelErrorReporter,
        register_groq_model_error_reporter,
    )
    from mcp_server.infrastructure.project_review_repository import ProjectReviewRepository
    from mcp_server.interface.custom_tools_project_review import (
        register_project_review_tool_repository,
    )

    project_review_repo = ProjectReviewRepository(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    register_project_review_repository(project_review_repo)
    register_project_review_tool_repository(project_review_repo)
    register_groq_model_error_reporter(
        GroqModelErrorReporter(settings.supabase_url, settings.supabase_service_role_key)
    )

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


def _lazy_build_search_client(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> ISearchClient:
    return build_search_client(settings, cache)  # type: ignore[arg-type]


def _lazy_build_video_client(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IVideoSearchClient:
    return build_video_client(settings, cache)  # type: ignore[arg-type]


def _lazy_build_embedding_provider(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IEmbeddingProvider:
    return build_embedding_provider(settings, cache)  # type: ignore[arg-type]


def _lazy_build_vector_retriever(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IVectorRetriever:
    return build_vector_retriever(settings, cache)  # type: ignore[arg-type]


def _lazy_build_vector_index_writer(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IVectorIndexWriter:
    _ = cache
    return build_vector_index_writer(settings)  # type: ignore[arg-type]


def _lazy_build_reranker(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IReranker:
    _ = cache
    return build_reranker(settings)  # type: ignore[arg-type]


def _lazy_build_chunking_strategy(
    settings: WorkflowSettings,
    cache: ICacheStore | None,
) -> IChunkingStrategy:
    _ = cache
    return build_chunking_strategy(settings)  # type: ignore[arg-type]


register_chat_model_builder(_lazy_build_chat_model)
register_document_video_workflow_builder(_lazy_build_document_video_workflow)
register_search_client_builder(_lazy_build_search_client)
register_video_client_builder(_lazy_build_video_client)
register_embedding_provider_builder(_lazy_build_embedding_provider)
register_vector_retriever_builder(_lazy_build_vector_retriever)
register_vector_index_writer_builder(_lazy_build_vector_index_writer)
register_reranker_builder(_lazy_build_reranker)
register_chunking_strategy_builder(_lazy_build_chunking_strategy)
