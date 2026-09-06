"""Typed application configuration validated at startup."""

from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_HTTP_MCP_TRANSPORTS = frozenset({"http", "sse", "streamable-http"})


class Settings(BaseSettings):
    """Typed configuration validated at startup."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "VITE_SUPABASE_ANON_KEY"),
    )
    youtube_api_key: SecretStr | None = Field(default=None, alias="YOUTUBE_API_KEY")
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    llm_model: str | None = Field(
        default=None,
        alias="LLM_MODEL",
        description=(
            "Optional legacy pin; ignored for normal routing. "
            "Candidates come from list_active_groq_models by complexity."
        ),
    )
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)
    llm_complexity: int = Field(default=2, alias="LLM_COMPLEXITY", ge=1, le=3)
    llm_router_debounce_seconds: float = Field(
        default=0.1,
        alias="LLM_ROUTER_DEBOUNCE_SECONDS",
        ge=0.0,
    )
    llm_router_max_fallbacks: int = Field(
        default=1,
        alias="LLM_ROUTER_MAX_FALLBACKS",
        ge=0,
    )
    external_request_limit_per_minute: int = Field(
        default=60,
        alias="EXTERNAL_REQUEST_LIMIT_PER_MINUTE",
        ge=1,
    )
    mcp_transport: Literal["stdio", "http", "sse", "streamable-http"] = Field(
        default="stdio",
        alias="MCP_TRANSPORT",
    )
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST", min_length=1)
    mcp_port: int = Field(default=8000, alias="MCP_PORT", gt=0, le=65535)
    mcp_stateless_http: bool = Field(default=False, alias="MCP_STATELESS_HTTP")
    mcp_host_origin_protection: bool | Literal["auto"] | None = Field(
        default=None,
        alias="MCP_HOST_ORIGIN_PROTECTION",
    )
    mcp_allowed_hosts: str = Field(default="", alias="MCP_ALLOWED_HOSTS")
    mcp_inbound_token: SecretStr | None = Field(default=None, alias="MCP_INBOUND_TOKEN")
    mcp_require_inbound_token: bool = Field(
        default=False,
        alias="MCP_REQUIRE_INBOUND_TOKEN",
    )
    mcp_require_caller_jwt: bool = Field(default=False, alias="MCP_REQUIRE_CALLER_JWT")
    mcp_inbound_limit_per_minute: int = Field(
        default=60,
        alias="MCP_INBOUND_LIMIT_PER_MINUTE",
        ge=1,
    )

    @field_validator("mcp_host_origin_protection", mode="before")
    @classmethod
    def parse_mcp_host_origin_protection(cls, value: object) -> bool | Literal["auto"] | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized == "auto":
            return "auto"
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        msg = "MCP_HOST_ORIGIN_PROTECTION must be true, false, auto, or empty"
        raise ValueError(msg)

    @model_validator(mode="before")
    @classmethod
    def default_http_auth_requirements(cls, data: Any) -> Any:
        """Fail closed on HTTP/SSE unless the flags are set explicitly."""
        if not isinstance(data, dict):
            return data
        transport_raw = data.get("mcp_transport", data.get("MCP_TRANSPORT", "stdio"))
        transport = str(transport_raw or "stdio").strip().lower()
        http_like = transport in _HTTP_MCP_TRANSPORTS
        inbound_keys = ("mcp_require_inbound_token", "MCP_REQUIRE_INBOUND_TOKEN")
        caller_keys = ("mcp_require_caller_jwt", "MCP_REQUIRE_CALLER_JWT")
        if not any(key in data and data[key] not in (None, "") for key in inbound_keys):
            data["MCP_REQUIRE_INBOUND_TOKEN"] = http_like
        if not any(key in data and data[key] not in (None, "") for key in caller_keys):
            data["MCP_REQUIRE_CALLER_JWT"] = http_like
        return data

    groq_active_model_list_cache_seconds: float = Field(
        default=60.0,
        alias="GROQ_ACTIVE_MODEL_LIST_CACHE_SECONDS",
        ge=0.0,
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    cache_enabled: bool = Field(default=False, alias="CACHE_ENABLED")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT", gt=0)
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")

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

    cache_key_prefix_youtube: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_YOUTUBE")
    cache_key_prefix_web: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_WEB")
    cache_key_prefix_mcp_tool: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_MCP_TOOL")
    cache_key_prefix_llm: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_LLM")

    def inbound_token_value(self) -> str:
        if self.mcp_inbound_token is None:
            return ""
        return self.mcp_inbound_token.get_secret_value().strip()

    def assert_inbound_token_if_required(self) -> None:
        if self.mcp_require_inbound_token and not self.inbound_token_value():
            msg = "MCP_INBOUND_TOKEN is required when MCP_REQUIRE_INBOUND_TOKEN=true"
            raise RuntimeError(msg)


def load_settings() -> Settings:
    """Validate and return application settings."""
    return Settings()  # type: ignore[call-arg]
