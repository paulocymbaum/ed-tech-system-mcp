"""Typed application configuration validated at startup."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration validated at startup."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    youtube_api_key: SecretStr | None = Field(default=None, alias="YOUTUBE_API_KEY")
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    llm_model: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)
    llm_complexity: int = Field(default=2, alias="LLM_COMPLEXITY", ge=1, le=3)
    llm_router_debounce_seconds: float = Field(
        default=0.1,
        alias="LLM_ROUTER_DEBOUNCE_SECONDS",
        ge=0.0,
    )
    groq_model_catalog_cache_path: str = Field(
        default=".cache/groq_model_catalog.json",
        alias="GROQ_MODEL_CATALOG_CACHE_PATH",
    )
    groq_model_catalog_ttl_days: int = Field(
        default=7,
        alias="GROQ_MODEL_CATALOG_TTL_DAYS",
        ge=1,
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    cache_enabled: bool = Field(default=False, alias="CACHE_ENABLED")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT", gt=0)
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")

    cache_ttl_supabase_find_documents: int | None = Field(
        default=None,
        alias="CACHE_TTL_SUPABASE_FIND_DOCUMENTS",
        gt=0,
    )
    cache_ttl_youtube_search_videos: int | None = Field(
        default=None,
        alias="CACHE_TTL_YOUTUBE_SEARCH_VIDEOS",
        gt=0,
    )
    cache_ttl_web_search: int | None = Field(default=None, alias="CACHE_TTL_WEB_SEARCH", gt=0)
    cache_ttl_mcp_tool: int | None = Field(default=None, alias="CACHE_TTL_MCP_TOOL", gt=0)
    cache_ttl_llm_completion: int | None = Field(
        default=None,
        alias="CACHE_TTL_LLM_COMPLETION",
        gt=0,
    )

    cache_key_prefix_supabase: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_SUPABASE")
    cache_key_prefix_youtube: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_YOUTUBE")
    cache_key_prefix_web: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_WEB")
    cache_key_prefix_mcp_tool: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_MCP_TOOL")
    cache_key_prefix_llm: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_LLM")
    cache_ttl_embedding_query: int | None = Field(
        default=None,
        alias="CACHE_TTL_EMBEDDING_QUERY",
        gt=0,
    )
    cache_ttl_vector_retrieve: int | None = Field(
        default=None,
        alias="CACHE_TTL_VECTOR_RETRIEVE",
        gt=0,
    )
    cache_key_prefix_embedding: str | None = Field(
        default=None,
        alias="CACHE_KEY_PREFIX_EMBEDDING",
    )
    cache_key_prefix_vector: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_VECTOR")

    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION", gt=0)
    embedding_warm_on_boot: bool = Field(default=False, alias="EMBEDDING_WARM_ON_BOOT")
    embedding_cache_dir: str = Field(default=".cache/fastembed", alias="EMBEDDING_CACHE_DIR")
    retrieval_mode: str = Field(default="hybrid", alias="RETRIEVAL_MODE")
    retrieve_limit: int = Field(default=20, alias="RETRIEVE_LIMIT", ge=1, le=100)
    rerank_enabled: bool = Field(default=False, alias="RERANK_ENABLED")
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")
    rerank_top_n: int = Field(default=6, alias="RERANK_TOP_N", ge=1, le=50)
    vector_store_backend: str = Field(default="auto", alias="VECTOR_STORE_BACKEND")
    supabase_vector_enabled: bool = Field(default=False, alias="SUPABASE_VECTOR_ENABLED")
    chroma_persist_path: str = Field(default=".cache/chromadb", alias="CHROMA_PERSIST_PATH")
    chroma_collection_name: str = Field(
        default="document_chunks",
        alias="CHROMA_COLLECTION_NAME",
    )


def load_settings() -> Settings:
    """Validate and return application settings."""
    return Settings()  # type: ignore[call-arg]
