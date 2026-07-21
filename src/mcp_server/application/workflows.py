"""Use-case orchestrators tying domain ports together."""

from mcp_server.domain.interfaces import IDataRepository, IVideoSearchClient
from mcp_server.domain.schemas import DocumentHit, VideoResult


class DocumentVideoWorkflow:
    """Merge document retrieval with complementary video discovery."""

    def __init__(
        self,
        repository: IDataRepository,
        video_client: IVideoSearchClient,
    ) -> None:
        self._repository = repository
        self._video_client = video_client

    async def retrieve_with_videos(
        self,
        query: str,
        document_limit: int = 10,
        video_limit: int = 5,
    ) -> tuple[list[DocumentHit], list[VideoResult]]:
        """Fetch documents and enrich with related educational videos."""
        documents = await self._repository.find_documents(query, limit=document_limit)
        search_terms = query
        if documents:
            search_terms = documents[0].title
        videos = await self._video_client.search_videos(
            search_terms,
            max_results=video_limit,
        )
        return documents, videos
