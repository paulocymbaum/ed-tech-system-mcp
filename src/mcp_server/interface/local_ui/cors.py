"""CORS policy for the workflow API when the UI is hosted on a remote platform."""

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

_HOSTED_PREVIEW_ORIGIN_REGEX = r"https://.*\.(onrender|vercel)\.app"


def _parse_csv_origins(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _allow_preview_deployments(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    preview_env = os.getenv("WORKFLOW_UI_ALLOW_PREVIEW_DEPLOYMENTS")
    if preview_env is None:
        preview_env = os.getenv("WORKFLOW_UI_ALLOW_VERCEL_PREVIEWS", "true")
    return preview_env.strip().lower() in {"1", "true", "yes", "on"}


def resolve_workflow_ui_cors(
    *,
    app_env: str | None = None,
    configured_origins: str | None = None,
    allow_preview_deployments: bool | None = None,
    allow_vercel_previews: bool | None = None,
) -> tuple[list[str], str | None]:
    """Return explicit CORS origins and an optional hosted preview regex."""
    env = (app_env or os.getenv("APP_ENV", "development")).strip().lower()
    configured = configured_origins if configured_origins is not None else os.getenv(
        "WORKFLOW_UI_CORS_ORIGINS",
        "",
    )
    allow_previews = _allow_preview_deployments(
        allow_preview_deployments if allow_preview_deployments is not None else allow_vercel_previews
    )

    origins: set[str] = set(_LOCAL_ORIGINS) if env in {"development", "local"} else set()
    origins.update(_parse_csv_origins(configured))

    regex = _HOSTED_PREVIEW_ORIGIN_REGEX if allow_previews and env in {
        "production",
        "staging",
        "ci",
    } else None
    return sorted(origins), regex
