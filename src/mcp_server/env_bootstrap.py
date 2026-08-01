"""Environment bootstrap shared by MCP entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def bootstrap_environment() -> None:
    """Load local .env in development only. OS environment always wins."""
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "development":
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
