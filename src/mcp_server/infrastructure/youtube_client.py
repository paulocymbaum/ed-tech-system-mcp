"""YouTube Data API adapter for educational video search."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import httplib2  # type: ignore[import-untyped]
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.interfaces import IVideoSearchClient
from mcp_server.domain.invariants import (
    require_credential,
    require_non_empty_text,
    require_positive_int,
)
from mcp_server.domain.schemas import VideoResult

_YOUTUBE_HTTP_TIMEOUT_SECONDS = 20.0


class YouTubeDataApiClient(IVideoSearchClient):
    """Adapter for YouTube Data API v3."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._lock = threading.Lock()
        self._youtube: Any = None

    def _youtube_resource(self) -> Any:
        with self._lock:
            if self._youtube is None:
                http = httplib2.Http(timeout=_YOUTUBE_HTTP_TIMEOUT_SECONDS)
                self._youtube = build(
                    "youtube",
                    "v3",
                    developerKey=self._api_key,
                    cache_discovery=False,
                    http=http,
                )
            return self._youtube

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        query = require_non_empty_text(query, field="query")
        max_results = require_positive_int(max_results, field="max_results")
        require_credential(self._api_key, resource="YouTube API")

        try:
            return await asyncio.to_thread(
                self._search_videos_sync,
                query,
                max_results,
                language,
                safe_search,
            )
        except HttpError as exc:
            if exc.resp.status in {401, 403}:
                raise ResourceNotFoundError("YouTube API credentials were rejected") from exc
            raise

    def _search_videos_sync(
        self,
        query: str,
        max_results: int,
        language: str,
        safe_search: bool,
    ) -> list[VideoResult]:
        youtube = self._youtube_resource()
        response = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                maxResults=max_results,
                type="video",
                safeSearch="strict" if safe_search else "none",
                relevanceLanguage=language,
            )
            .execute()
        )

        videos: list[VideoResult] = []
        for item in response.get("items", []):
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet")
            if not isinstance(snippet, dict):
                continue
            video_id = item.get("id", {}).get("videoId")
            if not isinstance(video_id, str) or not video_id:
                continue
            title = str(snippet.get("title", "")).strip()
            channel = str(snippet.get("channelTitle", "")).strip()
            if not title:
                continue
            videos.append(
                VideoResult(
                    title=title,
                    channel=channel or "Unknown channel",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                )
            )
        return videos
