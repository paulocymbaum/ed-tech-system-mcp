"""Persistence tests for the Groq model catalog cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp_server.domain.llm_routing import (
    GROQ_MODEL_CATALOG_TTL_DAYS,
    GROQ_MODEL_CATALOG_TTL_SECONDS,
    GroqModelCatalogEntry,
    GroqModelCatalogSnapshot,
    IGroqModelCatalogClient,
)
from mcp_server.infrastructure.groq_model_catalog import CachingGroqModelCatalogClient
from mcp_server.infrastructure.groq_model_catalog_cache import (
    FileGroqModelCatalogCache,
    InMemoryGroqModelCatalogCache,
    is_catalog_snapshot_fresh,
)


class _StaticGroqModelCatalog(IGroqModelCatalogClient):
    def __init__(self, entries: list[GroqModelCatalogEntry]) -> None:
        self._entries = entries

    def fetch_models(self) -> list[GroqModelCatalogEntry]:
        return list(self._entries)


def test_is_catalog_snapshot_fresh_within_seven_day_ttl() -> None:
    now = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    fetched_at = now - timedelta(days=GROQ_MODEL_CATALOG_TTL_DAYS - 1)
    assert is_catalog_snapshot_fresh(fetched_at, now=now) is True


def test_is_catalog_snapshot_fresh_expires_after_seven_days() -> None:
    now = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    fetched_at = now - timedelta(days=GROQ_MODEL_CATALOG_TTL_DAYS)
    assert is_catalog_snapshot_fresh(fetched_at, now=now) is False


def test_file_cache_round_trips_catalog_snapshot(tmp_path: Path) -> None:
    cache = FileGroqModelCatalogCache(tmp_path / "groq_model_catalog.json")
    entry = GroqModelCatalogEntry(
        model_id="allam-2-7b",
        display_name="ALLaM-2-7b",
        input_modalities=("text",),
        output_modalities=("text",),
        pricing=None,
    )
    snapshot = GroqModelCatalogSnapshot(
        fetched_at=datetime.now(tz=UTC),
        entries=[entry],
    )

    cache.save(snapshot)
    loaded = cache.load()

    assert loaded is not None
    assert loaded.fetched_at == snapshot.fetched_at
    assert loaded.entries == snapshot.entries


def test_file_cache_returns_none_when_snapshot_is_stale(tmp_path: Path) -> None:
    cache = FileGroqModelCatalogCache(tmp_path / "groq_model_catalog.json")
    stale_snapshot = GroqModelCatalogSnapshot(
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        entries=[
            GroqModelCatalogEntry(
                model_id="allam-2-7b",
                input_modalities=("text",),
                output_modalities=("text",),
            )
        ],
    )
    cache.save(stale_snapshot)

    assert cache.load() is None


def test_caching_catalog_client_uses_cache_without_calling_live_client() -> None:
    calls = {"count": 0}
    entry = GroqModelCatalogEntry(
        model_id="allam-2-7b",
        input_modalities=("text",),
        output_modalities=("text",),
    )
    live = _StaticGroqModelCatalog([entry])
    original_fetch = live.fetch_models

    def _counting_fetch() -> list[GroqModelCatalogEntry]:
        calls["count"] += 1
        return original_fetch()

    live.fetch_models = _counting_fetch  # type: ignore[method-assign]
    cache = InMemoryGroqModelCatalogCache()
    caching_client = CachingGroqModelCatalogClient(live, cache)

    first = caching_client.fetch_models()
    second = caching_client.fetch_models()

    assert first == second
    assert calls["count"] == 1


def test_caching_catalog_client_refreshes_after_cache_expires() -> None:
    calls = {"count": 0}
    entry = GroqModelCatalogEntry(
        model_id="allam-2-7b",
        input_modalities=("text",),
        output_modalities=("text",),
    )
    live = _StaticGroqModelCatalog([entry])
    original_fetch = live.fetch_models

    def _counting_fetch() -> list[GroqModelCatalogEntry]:
        calls["count"] += 1
        return original_fetch()

    live.fetch_models = _counting_fetch  # type: ignore[method-assign]
    cache = InMemoryGroqModelCatalogCache(ttl_seconds=60)
    caching_client = CachingGroqModelCatalogClient(live, cache)

    caching_client.fetch_models()
    cache.save(
        GroqModelCatalogSnapshot(
            fetched_at=datetime.now(tz=UTC) - timedelta(seconds=61),
            entries=[entry],
        )
    )
    caching_client.fetch_models()

    assert calls["count"] == 2


def test_default_file_cache_ttl_is_seven_days(tmp_path: Path) -> None:
    cache = FileGroqModelCatalogCache(tmp_path / "groq.json")
    assert cache._ttl_seconds == GROQ_MODEL_CATALOG_TTL_SECONDS  # noqa: SLF001
