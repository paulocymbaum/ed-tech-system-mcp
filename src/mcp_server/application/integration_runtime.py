"""Runtime accessors for wired search and video integration clients."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from mcp_server.domain.cache import ICacheStore
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient

_search_client: ISearchClient | None = None
_video_client: IVideoSearchClient | None = None
_lazy_settings: IntegrationSettings | None = None
_lazy_cache_store: ICacheStore | None = None
_search_builder: SearchClientBuilder | None = None
_video_builder: VideoClientBuilder | None = None


class IntegrationSettings(Protocol):
    """Settings subset required to build integration clients."""


SearchClientBuilder = Callable[[IntegrationSettings, ICacheStore | None], ISearchClient]
VideoClientBuilder = Callable[[IntegrationSettings, ICacheStore | None], IVideoSearchClient]


def register_search_client_builder(builder: SearchClientBuilder) -> None:
    """Register the composition-root search client builder (wiring only)."""
    global _search_builder
    _search_builder = builder


def register_video_client_builder(builder: VideoClientBuilder) -> None:
    """Register the composition-root video client builder (wiring only)."""
    global _video_builder
    _video_builder = builder


def reset_integration_client_builders() -> None:
    """Clear registered integration client builders (for tests)."""
    global _search_builder, _video_builder
    _search_builder = None
    _video_builder = None


def configure_lazy_integration_clients(
    settings: IntegrationSettings | None,
    cache_store: ICacheStore | None = None,
) -> None:
    """Store settings and cache for deferred client construction at first access."""
    global _lazy_settings, _lazy_cache_store, _search_client, _video_client
    _lazy_settings = settings
    _lazy_cache_store = cache_store
    _search_client = None
    _video_client = None


def set_search_client(client: ISearchClient | None) -> None:
    """Store a wired search client (for tests)."""
    global _search_client
    _search_client = client


def set_video_client(client: IVideoSearchClient | None) -> None:
    """Store a wired video client (for tests)."""
    global _video_client
    _video_client = client


def _build_client[T](
    current: T | None,
    builder: Callable[[IntegrationSettings, ICacheStore | None], T] | None,
) -> T | None:
    if current is not None:
        return current
    if _lazy_settings is None or builder is None:
        return None
    return builder(_lazy_settings, _lazy_cache_store)


def get_search_client() -> ISearchClient | None:
    """Return the search client, building lazily on first access when configured."""
    global _search_client
    built = _build_client(_search_client, _search_builder)
    if built is not None:
        _search_client = built
    return _search_client


def get_video_client() -> IVideoSearchClient | None:
    """Return the video client, building lazily on first access when configured."""
    global _video_client
    built = _build_client(_video_client, _video_builder)
    if built is not None:
        _video_client = built
    return _video_client


def reset_integration_clients() -> None:
    """Clear runtime clients and lazy-init state (for tests)."""
    global _search_client, _video_client, _lazy_settings, _lazy_cache_store
    _search_client = None
    _video_client = None
    _lazy_settings = None
    _lazy_cache_store = None
