"""Entrypoint — transport initialization and environment bootstrap."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_server.interface.custom_tools import health_check  # noqa: F401
from mcp_server.interface.mcp_server import create_mcp_server


def bootstrap_environment() -> None:
    """Load local .env in development only. OS environment always wins."""
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "development":
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)


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
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


def load_settings() -> Settings:
    """Validate and return application settings."""
    return Settings()  # type: ignore[call-arg]


def main() -> None:
    """Bootstrap environment, validate settings, and start the MCP server."""
    bootstrap_environment()
    _settings = load_settings()
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
