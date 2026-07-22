"""Groq model catalog client."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from pydantic import SecretStr

from mcp_server.domain.llm_routing import (
    GroqModelCatalogEntry,
    GroqModelCatalogSnapshot,
    GroqModelPricing,
    IGroqModelCatalogCache,
    IGroqModelCatalogClient,
)

_GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"


def _parse_pricing(raw: object) -> GroqModelPricing | None:
    if not isinstance(raw, dict):
        return None
    return GroqModelPricing(
        prompt=float(raw.get("prompt") or 0),
        completion=float(raw.get("completion") or 0),
        request=float(raw.get("request") or 0),
        image=float(raw.get("image") or 0),
    )


def _parse_modalities(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(item) for item in raw)


def catalog_entry_from_api_item(item: dict[str, object]) -> GroqModelCatalogEntry | None:
    """Build a catalog entry from a Groq /v1/models payload item."""
    model_id = item.get("id")
    if not model_id:
        return None
    display_name = str(item.get("name") or model_id)
    return GroqModelCatalogEntry(
        model_id=str(model_id),
        owned_by=str(item.get("owned_by", "")),
        display_name=display_name,
        input_modalities=_parse_modalities(item.get("input_modalities")),
        output_modalities=_parse_modalities(item.get("output_modalities")),
        pricing=_parse_pricing(item.get("pricing")),
    )


class GroqModelCatalogClient(IGroqModelCatalogClient):
    """Fetch the live Groq model list via the OpenAI-compatible models endpoint."""

    def __init__(self, api_key: SecretStr, *, timeout_seconds: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def fetch_models(self) -> list[GroqModelCatalogEntry]:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.get(_GROQ_MODELS_URL, headers=headers)
            response.raise_for_status()
            payload = response.json()

        entries: list[GroqModelCatalogEntry] = []
        for item in payload.get("data", []):
            if not isinstance(item, dict):
                continue
            entry = catalog_entry_from_api_item(item)
            if entry is not None:
                entries.append(entry)
        return entries


class CachingGroqModelCatalogClient(IGroqModelCatalogClient):
    """Fetch Groq models from cache when fresh, otherwise refresh from the API."""

    def __init__(
        self,
        live_client: IGroqModelCatalogClient,
        cache: IGroqModelCatalogCache,
    ) -> None:
        self._live_client = live_client
        self._cache = cache

    def fetch_models(self) -> list[GroqModelCatalogEntry]:
        cached = self._cache.load()
        if cached is not None:
            return list(cached.entries)

        entries = self._live_client.fetch_models()
        self._cache.save(
            GroqModelCatalogSnapshot(
                fetched_at=datetime.now(tz=UTC),
                entries=entries,
            )
        )
        return entries
