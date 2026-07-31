"""CORS policy for the workflow API when the UI is hosted on Vercel."""

from __future__ import annotations

import os

_LOCAL_ORIGINS = frozenset(
    {
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:8877",
        "http://localhost:8877",
    }
)

_VERCEL_PREVIEW_ORIGIN_REGEX = r"https://.*\.vercel\.app"


def _parse_csv_origins(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def resolve_workflow_ui_cors(
    *,
    app_env: str | None = None,
    configured_origins: str | None = None,
    allow_vercel_previews: bool | None = None,
) -> tuple[list[str], str | None]:
    """Return explicit CORS origins and an optional Vercel preview regex."""
    env = (app_env or os.getenv("APP_ENV", "development")).strip().lower()
    configured = configured_origins if configured_origins is not None else os.getenv(
        "WORKFLOW_UI_CORS_ORIGINS",
        "",
    )
    if allow_vercel_previews is None:
        allow_vercel_previews = os.getenv("WORKFLOW_UI_ALLOW_VERCEL_PREVIEWS", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    origins: set[str] = set(_LOCAL_ORIGINS) if env in {"development", "local"} else set()
    origins.update(_parse_csv_origins(configured))

    regex = _VERCEL_PREVIEW_ORIGIN_REGEX if allow_vercel_previews and env in {
        "production",
        "staging",
        "ci",
    } else None
    return sorted(origins), regex
