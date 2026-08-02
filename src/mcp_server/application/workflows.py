"""Use-case orchestrators tying domain ports together."""

import asyncio
import contextlib

from mcp_server.domain.interfaces import IDataRepository, IVideoSearchClient
from mcp_server.domain.schemas import ChunkRetrievalFilter, DocumentHit, VideoResult


class DocumentVideoWorkflow:
    """Merge document retrieval with complementary video discovery."""

    def __init__(
        self,
        repository: IDataRepository,
        video_client: IVideoSearchClient,
    ) -> None:
        self._repository = repository
        self._video_client = video_client

    async def fetch_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        tenant_id: str | None = None,
    ) -> list[DocumentHit]:
        """Fetch documents matching the query."""
        filters = ChunkRetrievalFilter(tenant_id=tenant_id) if tenant_id else None
        return await self._repository.find_documents(query, limit=limit, filters=filters)

    @staticmethod
    def derive_search_terms(query: str, documents: list[DocumentHit]) -> str:
        """Derive video search terms from documents or fall back to the query."""
        if documents:
            return documents[0].title
        return query

    async def search_videos(
        self,
        search_terms: str,
        video_limit: int = 5,
        *,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        """Search for educational videos using the given terms."""
        return await self._video_client.search_videos(
            search_terms,
            max_results=video_limit,
            language=language,
            safe_search=safe_search,
        )

    async def retrieve_with_videos(
        self,
        query: str,
        document_limit: int = 10,
        video_limit: int = 5,
        *,
        tenant_id: str | None = None,
    ) -> tuple[list[DocumentHit], list[VideoResult]]:
        """Fetch documents and enrich with related educational videos.

        Latency trade-off: document and video port calls always start in parallel
        using the user query as provisional video terms. When the first document
        supplies a different title, a second sequential YouTube call replaces the
        provisional results. When no documents are returned, the parallel video
        search is kept (query-only path) with no extra round trip.

        For per-node graph observability or workflow timeout enforcement, use
        ``run_document_video_graph`` instead (sequential port calls per node).
        """
        documents_task = asyncio.create_task(
            self.fetch_documents(query, document_limit, tenant_id=tenant_id),
        )
        videos_task = asyncio.create_task(self.search_videos(query, video_limit))
        documents = await documents_task

        if not documents:
            videos = await videos_task
            return documents, videos

        search_terms = self.derive_search_terms(query, documents)
        if search_terms == query:
            videos = await videos_task
            return documents, videos

        videos_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await videos_task
        videos = await self.search_videos(search_terms, video_limit)
        return documents, videos
