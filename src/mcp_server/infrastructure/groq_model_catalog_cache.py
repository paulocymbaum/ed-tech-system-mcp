"""Persistence for Groq model catalog snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from mcp_server.domain.llm_routing import (
    GROQ_MODEL_CATALOG_TTL_SECONDS,
    GroqModelCatalogEntry,
    GroqModelCatalogSnapshot,
    GroqModelPricing,
    IGroqModelCatalogCache,
)

_DEFAULT_CACHE_PATH = Path(".cache") / "groq_model_catalog.json"


class _GroqModelPricingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: float = 0.0
    completion: float = 0.0
    request: float = 0.0
    image: float = 0.0


class _GroqModelCatalogEntryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    owned_by: str = ""
    display_name: str = ""
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
    pricing: _GroqModelPricingPayload | None = None


class GroqModelCatalogCacheEnvelope(BaseModel):
    """JSON envelope for on-disk Groq catalog snapshots."""

    model_config = ConfigDict(extra="forbid")

    fetched_at: datetime
    models: list[_GroqModelCatalogEntryPayload]

    @classmethod
    def from_snapshot(cls, snapshot: GroqModelCatalogSnapshot) -> GroqModelCatalogCacheEnvelope:
        return cls(
            fetched_at=snapshot.fetched_at,
            models=[_entry_to_payload(entry) for entry in snapshot.entries],
        )

    def to_snapshot(self) -> GroqModelCatalogSnapshot:
        return GroqModelCatalogSnapshot(
            fetched_at=self.fetched_at,
            entries=[_entry_from_payload(payload) for payload in self.models],
        )


def _entry_to_payload(entry: GroqModelCatalogEntry) -> _GroqModelCatalogEntryPayload:
    pricing = None
    if entry.pricing is not None:
        pricing = _GroqModelPricingPayload(
            prompt=entry.pricing.prompt,
            completion=entry.pricing.completion,
            request=entry.pricing.request,
            image=entry.pricing.image,
        )
    return _GroqModelCatalogEntryPayload(
        model_id=entry.model_id,
        owned_by=entry.owned_by,
        display_name=entry.display_name,
        input_modalities=list(entry.input_modalities),
        output_modalities=list(entry.output_modalities),
        pricing=pricing,
    )


def _entry_from_payload(payload: _GroqModelCatalogEntryPayload) -> GroqModelCatalogEntry:
    pricing = None
    if payload.pricing is not None:
        pricing = GroqModelPricing(
            prompt=payload.pricing.prompt,
            completion=payload.pricing.completion,
            request=payload.pricing.request,
            image=payload.pricing.image,
        )
    return GroqModelCatalogEntry(
        model_id=payload.model_id,
        owned_by=payload.owned_by,
        display_name=payload.display_name,
        input_modalities=tuple(payload.input_modalities),
        output_modalities=tuple(payload.output_modalities),
        pricing=pricing,
    )


def is_catalog_snapshot_fresh(
    fetched_at: datetime,
    *,
    now: datetime | None = None,
    ttl_seconds: int = GROQ_MODEL_CATALOG_TTL_SECONDS,
) -> bool:
    """Return whether a snapshot is still within the configured TTL."""
    current = now or datetime.now(tz=UTC)
    normalized_fetched_at = (
        fetched_at if fetched_at.tzinfo is not None else fetched_at.replace(tzinfo=UTC)
    )
    return current - normalized_fetched_at < timedelta(seconds=ttl_seconds)


class FileGroqModelCatalogCache(IGroqModelCatalogCache):
    """Persist catalog snapshots to a JSON file for multi-day reuse."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        ttl_seconds: int = GROQ_MODEL_CATALOG_TTL_SECONDS,
    ) -> None:
        self._path = Path(path or _DEFAULT_CACHE_PATH)
        self._ttl_seconds = ttl_seconds

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> GroqModelCatalogSnapshot | None:
        if not self._path.is_file():
            return None
        try:
            payload = self._path.read_text(encoding="utf-8")
            envelope = GroqModelCatalogCacheEnvelope.model_validate_json(payload)
        except (OSError, ValueError):
            return None
        if not is_catalog_snapshot_fresh(
            envelope.fetched_at,
            ttl_seconds=self._ttl_seconds,
        ):
            return None
        return envelope.to_snapshot()

    def save(self, snapshot: GroqModelCatalogSnapshot) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        envelope = GroqModelCatalogCacheEnvelope.from_snapshot(snapshot)
        temp_path = self._path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(envelope.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._path)

    def clear(self) -> None:
        if self._path.is_file():
            self._path.unlink()


class InMemoryGroqModelCatalogCache(IGroqModelCatalogCache):
    """Process-local catalog cache for tests."""

    def __init__(self, *, ttl_seconds: int = GROQ_MODEL_CATALOG_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._snapshot: GroqModelCatalogSnapshot | None = None

    def load(self) -> GroqModelCatalogSnapshot | None:
        if self._snapshot is None:
            return None
        if not is_catalog_snapshot_fresh(
            self._snapshot.fetched_at,
            ttl_seconds=self._ttl_seconds,
        ):
            self._snapshot = None
            return None
        return self._snapshot

    def save(self, snapshot: GroqModelCatalogSnapshot) -> None:
        self._snapshot = snapshot

    def clear(self) -> None:
        self._snapshot = None
