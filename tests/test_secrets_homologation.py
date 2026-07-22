"""Live homologation for Doppler / .env secrets against external services.

Run only when you intend to hit real APIs:

    doppler run -- env RUN_SECRETS_HOMOLOGATION=1 uv run pytest tests/test_secrets_homologation.py -v

Or with a local gitignored .env (APP_ENV=development):

    RUN_SECRETS_HOMOLOGATION=1 uv run pytest tests/test_secrets_homologation.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from mcp_server.settings import Settings, load_settings
from mcp_server.wiring import resolve_redis_url

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SECRET_NAMES = frozenset(
    {
        "APP_ENV",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "YOUTUBE_API_KEY",
        "GROQ_API_KEY",
        "LOG_LEVEL",
    }
)

OPTIONAL_SECRET_NAMES = frozenset(
    {
        "TAVILY_API_KEY",
        "CACHE_ENABLED",
        "REDIS_URL",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_PASSWORD",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
    }
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SECRETS_HOMOLOGATION") != "1",
    reason="Set RUN_SECRETS_HOMOLOGATION=1 to run live secret validation",
)


@pytest.fixture(scope="module")
def settings() -> Settings:
    if os.getenv("APP_ENV", "development") == "development":
        env_path = REPO_ROOT / ".env"
        if env_path.is_file():
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_path, override=False)
    return load_settings()


def test_h01_settings_required_fields_present(settings: Settings) -> None:
    assert settings.supabase_url.strip()
    assert settings.supabase_service_role_key.get_secret_value().strip()
    assert settings.youtube_api_key is not None
    assert settings.youtube_api_key.get_secret_value().strip()
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value().strip()


def test_h02_doppler_lists_required_secret_names() -> None:
    if not _doppler_available():
        pytest.skip("doppler CLI not installed")

    names = _doppler_secret_names()
    missing = sorted(REQUIRED_SECRET_NAMES - names)
    assert not missing, f"Doppler config missing required secrets: {missing}"


def test_h03_supabase_credentials_accepted(settings: Settings) -> None:
    url = settings.supabase_url.rstrip("/")
    key = settings.supabase_service_role_key.get_secret_value()
    try:
        response = httpx.get(
            f"{url}/rest/v1/",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15.0,
        )
    except httpx.ConnectError as exc:
        pytest.fail(
            f"Supabase URL is unreachable ({url}): {exc}. "
            "Check the project is active and SUPABASE_URL is correct in Doppler."
        )
    assert response.status_code != 401, "Supabase rejected the service role key"
    assert response.status_code in {200, 404}, f"Unexpected Supabase response: {response.status_code}"


def test_h04_youtube_api_key_accepted(settings: Settings) -> None:
    api_key = settings.youtube_api_key
    assert api_key is not None
    youtube = build("youtube", "v3", developerKey=api_key.get_secret_value(), cache_discovery=False)
    try:
        youtube.search().list(part="id", q="education", maxResults=1, type="video").execute()
    except HttpError as exc:
        if exc.resp.status in {403, 401}:
            pytest.fail(f"YouTube API key rejected: HTTP {exc.resp.status}")
        raise


def test_h05_groq_api_key_accepted(settings: Settings) -> None:
    api_key = settings.groq_api_key
    assert api_key is not None
    response = httpx.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key.get_secret_value()}"},
        timeout=15.0,
    )
    assert response.status_code == 200, f"Groq API key rejected: HTTP {response.status_code}"


@pytest.mark.skipif(
    not os.getenv("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY not set",
)
def test_h06_tavily_api_key_accepted(settings: Settings) -> None:
    api_key = settings.tavily_api_key
    assert api_key is not None
    key = api_key.get_secret_value().strip()
    if not key:
        pytest.skip("TAVILY_API_KEY empty")

    response = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": "education", "max_results": 1},
        timeout=15.0,
    )
    assert response.status_code == 200, f"Tavily API key rejected: HTTP {response.status_code}"


@pytest.mark.skipif(
    os.getenv("CACHE_ENABLED", "false").lower() not in {"1", "true", "yes"},
    reason="CACHE_ENABLED is false",
)
def test_h07_redis_reachable_when_cache_enabled(settings: Settings) -> None:
    import redis

    redis_url = resolve_redis_url(settings)
    if not redis_url:
        pytest.skip("No Redis URL configured")

    client = redis.from_url(redis_url, socket_connect_timeout=3)
    assert client.ping() is True


def _doppler_available() -> bool:
    from shutil import which

    return which("doppler") is not None


def _doppler_secret_names() -> set[str]:
    import json
    import subprocess

    project = os.getenv("DOPPLER_PROJECT", "ed-harness-system")
    config = os.getenv("DOPPLER_CONFIG", "dev")
    result = subprocess.run(
        [
            "doppler",
            "secrets",
            "download",
            "--no-file",
            "--format",
            "json",
            "--project",
            project,
            "--config",
            config,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return {key for key in payload if not key.startswith("DOPPLER_")}
