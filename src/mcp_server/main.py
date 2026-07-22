"""Entrypoint — transport initialization and environment bootstrap."""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from mcp_server.interface.custom_tools import (  # noqa: F401
    find_documents,
    health_check,
    run_workflow,
    search_youtube,
)
from mcp_server.interface.mcp_server import create_mcp_server
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import Settings, load_settings
from mcp_server.wiring import initialize_application_runtime


def bootstrap_environment() -> None:
    """Load local .env in development only. OS environment always wins."""
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "development":
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)


def configure_logging(settings: Settings) -> None:
    """Apply root log level from validated settings."""
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(level=level, force=True)


def bootstrap_application_runtime() -> None:
    """Load settings, operational config, and wire the composition root."""
    settings = load_settings()
    configure_logging(settings)
    operational_config = load_operational_config()
    initialize_application_runtime(operational_config, settings)


def main() -> None:
    """Bootstrap environment, validate settings, and start the MCP server."""
    bootstrap_environment()
    bootstrap_application_runtime()
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
