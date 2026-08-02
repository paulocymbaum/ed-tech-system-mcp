"""Environment bootstrap shared by MCP entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def repo_root() -> Path:
    """Repository root (parent of ``src/``)."""
    return Path(__file__).resolve().parents[2]


def bootstrap_environment() -> None:
    """Load local dotenv files in development only. OS environment always wins.

    Load order (``override=False`` — first file wins on duplicate keys):

    1. ``.env`` — Doppler download or hand-edited app secrets
    2. ``.env.local`` — machine-specific overlays (e.g. Render deploy metadata, local ports)
    """
    app_env = os.getenv("APP_ENV", "development")

    if app_env != "development":
        return

    root = repo_root()
    for env_name in (".env", ".env.local"):
        load_dotenv(dotenv_path=root / env_name, override=False)
