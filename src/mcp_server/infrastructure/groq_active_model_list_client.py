"""Supabase-backed active Groq model list client."""

from __future__ import annotations

import time
from typing import Any, cast

from pydantic import SecretStr
from supabase import Client, create_client

from mcp_server.domain.invariants import require_credential
from mcp_server.domain.llm_routing import (
    GroqActiveModel,
    IGroqActiveModelListClient,
    normalize_complexity_tiers,
)


def parse_active_models_payload(payload: object) -> list[GroqActiveModel]:
    """Defensively parse ``list_active_groq_models`` / edge-shaped payloads."""
    rows: list[object]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        models = payload.get("models")
        if isinstance(models, list):
            rows = models
        elif isinstance(payload.get("data"), dict):
            nested = cast(dict[str, Any], payload["data"]).get("models")
            rows = nested if isinstance(nested, list) else []
        else:
            rows = []
    else:
        rows = []

    parsed: list[GroqActiveModel] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        model_id = item.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        complexity = normalize_complexity_tiers(item.get("complexity"))
        if complexity is None:
            continue
        parsed.append(GroqActiveModel(model_id=model_id.strip(), complexity=complexity))
    return parsed


class SupabaseGroqActiveModelListClient(IGroqActiveModelListClient):
    """Fetch active models via PostgREST RPC ``list_active_groq_models``."""

    def __init__(self, supabase_url: str, service_role_key: SecretStr | str) -> None:
        self._supabase_url = supabase_url
        if isinstance(service_role_key, SecretStr):
            self._service_role_key = service_role_key.get_secret_value()
        else:
            self._service_role_key = service_role_key
        self._client: Client | None = None

    def _client_or_create(self) -> Client:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        if self._client is None:
            self._client = create_client(self._supabase_url, self._service_role_key)
        return self._client

    def fetch_active_models(self) -> list[GroqActiveModel]:
        response = self._client_or_create().rpc("list_active_groq_models", {}).execute()
        return parse_active_models_payload(response.data)


class CachingGroqActiveModelListClient(IGroqActiveModelListClient):
    """In-process TTL cache around an active-model list client."""

    def __init__(self, live: IGroqActiveModelListClient, *, ttl_seconds: float = 60.0) -> None:
        self._live = live
        self._ttl_seconds = ttl_seconds
        self._cached_at: float | None = None
        self._cached: list[GroqActiveModel] | None = None

    def fetch_active_models(self) -> list[GroqActiveModel]:
        now = time.monotonic()
        if (
            self._cached is not None
            and self._cached_at is not None
            and (now - self._cached_at) < self._ttl_seconds
        ):
            return list(self._cached)
        models = self._live.fetch_active_models()
        self._cached = list(models)
        self._cached_at = now
        return list(models)

    def clear(self) -> None:
        """Drop the cached snapshot (tests)."""
        self._cached = None
        self._cached_at = None
