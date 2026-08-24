"""Use-case orchestrators tying domain ports together."""

import hashlib
import re

from mcp_server.domain.interfaces import IDataRepository, ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import ChunkRetrievalFilter, DocumentHit, VideoResult


class DocumentVideoWorkflow:
    """Merge document retrieval with complementary video discovery."""

    def __init__(
        self,
        repository: IDataRepository,
        video_client: IVideoSearchClient,
        search_client: ISearchClient | None = None,
    ) -> None:
        self._repository = repository
        self._video_client = video_client
        self._search_client = search_client

    async def fetch_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        tenant_id: str | None = None,
        course_id: str | None = None,
    ) -> list[DocumentHit]:
        """Fetch documents matching the query."""
        filters = self._build_filters(tenant_id, course_id)
        return await self._repository.find_documents(query, limit=limit, filters=filters)

    @staticmethod
    def _build_filters(
        tenant_id: str | None,
        course_id: str | None,
    ) -> ChunkRetrievalFilter | None:
        return (
            ChunkRetrievalFilter(tenant_id=tenant_id, course_id=course_id)
            if tenant_id or course_id
            else None
        )

    @staticmethod
    def derive_search_terms(query: str, documents: list[DocumentHit]) -> str:
        """Derive video search terms from documents or fall back to the query."""
        if documents:
            return documents[0].title
        return query

    @staticmethod
    def _web_snippet_to_document_hit(snippet: str) -> DocumentHit | None:
        """Best-effort parse of a web search snippet into a DocumentHit.

        Tavily returns ``title — content — url``. When a URL is present, the id
        is set to the URL so the frontend can open it as an external link.
        """
        parts = [part.strip() for part in snippet.split(" — ") if part.strip()]
        if not parts:
            return None

        url: str | None = None
        if parts[-1].startswith(("http://", "https://")):
            url = parts.pop()

        title = parts[0]
        content = " — ".join(parts[1:]) if len(parts) > 1 else title
        doc_id = url or f"web:{hashlib.sha256(snippet.encode()).hexdigest()[:16]}"
        metadata: dict[str, str] = {"source": "web_search"}
        if url:
            metadata["url"] = url

        return DocumentHit(id=doc_id, title=title, content=content, metadata=metadata)

    async def _search_web_documents(
        self,
        query: str,
        limit: int,
    ) -> list[DocumentHit]:
        """Fetch web search results as document hits when the local RAG index is empty."""
        if self._search_client is None:
            return []
        snippets = await self._search_client.search(query, max_results=limit)
        hits: list[DocumentHit] = []
        for snippet in snippets:
            hit = self._web_snippet_to_document_hit(snippet)
            if hit is not None:
                hits.append(hit)
        return hits[:limit]

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
        course_id: str | None = None,
    ) -> tuple[list[DocumentHit], list[VideoResult]]:
        """Fetch documents, then search videos using derived terms.

        When no local documents exist (or the local search returns empty) and a
        web search client is available, Tavily/DuckDuckGo results are returned as
        document hits instead. This avoids loading the embedding ONNX model on an
        empty index and surfaces external links during lesson creation.
        """
        filters = self._build_filters(tenant_id, course_id)
        documents: list[DocumentHit] = []

        if self._search_client is not None:
            has_local = await self._repository.has_documents(filters=filters)
            if has_local:
                documents = await self._repository.find_documents(
                    query, document_limit, filters=filters
                )
            if not documents:
                documents = await self._search_web_documents(query, document_limit)
        else:
            documents = await self._repository.find_documents(
                query, document_limit, filters=filters
            )

        search_terms = self.derive_search_terms(query, documents)
        videos = await self.search_videos(search_terms, video_limit)
        return documents, videos
