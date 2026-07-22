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


def load_settings() -> Settings:
    """Validate and return application settings."""
    return Settings()  # type: ignore[call-arg]
