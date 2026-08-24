"""Application workflow contract tests (T15–T19)."""

import asyncio

from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.interfaces import IDataRepository, ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import DocumentHit, VideoResult


class FakeRepository(IDataRepository):
    def __init__(self, documents: list[DocumentHit]) -> None:
        self._documents = documents
        self.last_query: str | None = None
        self.last_limit: int | None = None
        self.in_flight = 0
        self.max_in_flight = 0
        self.find_documents_called = False

    async def has_documents(self, *, filters=None) -> bool:
        return bool(self._documents)

    async def find_documents(self, query: str, limit: int = 10, *, filters=None) -> list[DocumentHit]:
        self.find_documents_called = True
        self.last_query = query
        self.last_limit = limit
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return self._documents


class FakeVideoClient(IVideoSearchClient):
    def __init__(self, videos: list[VideoResult]) -> None:
        self._videos = videos
        self.last_query: str | None = None
        self.last_max_results: int | None = None
        self.call_count = 0
        self.in_flight = 0
        self.max_in_flight = 0

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        self.last_query = query
        self.last_max_results = max_results
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        self.call_count += 1
        return self._videos


class FakeSearchClient(ISearchClient):
    def __init__(self, snippets: list[str]) -> None:
        self._snippets = snippets
        self.last_query: str | None = None
        self.last_max_results: int | None = None

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        self.last_query = query
        self.last_max_results = max_results
        return self._snippets[:max_results]


async def test_t15_workflow_uses_first_document_title_for_video_search() -> None:
    doc = DocumentHit(id="1", title="Photosynthesis Basics", content="...")
    repo = FakeRepository([doc])
    videos = [VideoResult(title="V", channel="C", url="https://example.com")]
    client = FakeVideoClient(videos)
    workflow = DocumentVideoWorkflow(repo, client)

    documents, result_videos = await workflow.retrieve_with_videos("plants")

    assert documents == [doc]
    assert result_videos == videos
    assert client.last_query == "Photosynthesis Basics"


async def test_t16_workflow_falls_back_to_query_when_no_documents() -> None:
    repo = FakeRepository([])
    client = FakeVideoClient([])
    workflow = DocumentVideoWorkflow(repo, client)

    await workflow.retrieve_with_videos("plants")

    assert client.last_query == "plants"


async def test_t17_workflow_routes_document_limit() -> None:
    repo = FakeRepository([])
    client = FakeVideoClient([])
    workflow = DocumentVideoWorkflow(repo, client)

    await workflow.retrieve_with_videos("query", document_limit=3)

    assert repo.last_limit == 3


async def test_t18_workflow_routes_video_limit() -> None:
    repo = FakeRepository([])
    client = FakeVideoClient([])
    workflow = DocumentVideoWorkflow(repo, client)

    await workflow.retrieve_with_videos("query", video_limit=2)

    assert client.last_max_results == 2


async def test_t19_workflow_returns_documents_and_videos_tuple() -> None:
    docs = [DocumentHit(id="1", title="T", content="C")]
    vids = [VideoResult(title="V", channel="Ch", url="https://example.com")]
    repo = FakeRepository(docs)
    client = FakeVideoClient(vids)
    workflow = DocumentVideoWorkflow(repo, client)

    result = await workflow.retrieve_with_videos("query")

    assert isinstance(result, tuple)
    assert result[0] == docs
    assert result[1] == vids


async def test_t19b_video_search_waits_for_documents() -> None:
    class SequentialTracker:
        def __init__(self) -> None:
            self.doc_finished = False
            self.video_started_after_doc = False

    tracker = SequentialTracker()

    class TrackingRepository(IDataRepository):
        async def find_documents(self, query: str, limit: int = 10, *, filters=None) -> list[DocumentHit]:
            await asyncio.sleep(0.02)
            tracker.doc_finished = True
            return []

    class TrackingVideoClient(IVideoSearchClient):
        async def search_videos(
            self,
            query: str,
            max_results: int = 5,
            language: str = "en",
            safe_search: bool = True,
        ) -> list[VideoResult]:
            tracker.video_started_after_doc = tracker.doc_finished
            return []

    workflow = DocumentVideoWorkflow(TrackingRepository(), TrackingVideoClient())

    await workflow.retrieve_with_videos("plants")

    assert tracker.video_started_after_doc is True


async def test_t19c_sequential_video_refetch_when_document_title_differs() -> None:
    doc = DocumentHit(id="1", title="Photosynthesis Basics", content="...")
    repo = FakeRepository([doc])
    client = FakeVideoClient([VideoResult(title="V", channel="C", url="https://example.com")])

    async def slow_search_videos(
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        client.last_query = query
        client.last_max_results = max_results
        await asyncio.sleep(0.1)
        client.call_count += 1
        return client._videos

    client.search_videos = slow_search_videos  # type: ignore[method-assign]
    workflow = DocumentVideoWorkflow(repo, client)

    await workflow.retrieve_with_videos("plants")

    assert client.call_count == 1
    assert client.last_query == "Photosynthesis Basics"


async def test_t19d_skips_second_video_fetch_when_title_matches_query() -> None:
    doc = DocumentHit(id="1", title="plants", content="...")
    repo = FakeRepository([doc])
    client = FakeVideoClient([])
    workflow = DocumentVideoWorkflow(repo, client)

    await workflow.retrieve_with_videos("plants")

    assert client.call_count == 1
    assert client.last_query == "plants"


async def test_t19e_workflow_falls_back_to_web_search_when_repository_is_empty() -> None:
    repo = FakeRepository([])
    videos = [VideoResult(title="V", channel="C", url="https://example.com/video")]
    video_client = FakeVideoClient(videos)
    web_client = FakeSearchClient(["Plants — All about plants — https://example.com/plants"])
    workflow = DocumentVideoWorkflow(repo, video_client, web_client)

    documents, result_videos = await workflow.retrieve_with_videos("plants", document_limit=2)

    assert not repo.find_documents_called
    assert len(documents) == 1
    assert documents[0].title == "Plants"
    assert documents[0].id == "https://example.com/plants"
    assert result_videos == videos
    assert video_client.last_query == "Plants"
    assert web_client.last_query == "plants"
    assert web_client.last_max_results == 2


async def test_t19f_workflow_prefers_local_documents_over_web_search() -> None:
    doc = DocumentHit(id="1", title="Photosynthesis Basics", content="...")
    repo = FakeRepository([doc])
    web_client = FakeSearchClient(["Web result — content — https://example.com/web"])
    video_client = FakeVideoClient([VideoResult(title="V", channel="C", url="https://example.com")])
    workflow = DocumentVideoWorkflow(repo, video_client, web_client)

    documents, _ = await workflow.retrieve_with_videos("plants")

    assert repo.find_documents_called
    assert documents == [doc]
    assert web_client.last_query is None


async def test_t19g_workflow_parses_tavily_snippet_without_url() -> None:
    repo = FakeRepository([])
    video_client = FakeVideoClient([])
    web_client = FakeSearchClient(["Just a title and content"])
    workflow = DocumentVideoWorkflow(repo, video_client, web_client)

    documents, _ = await workflow.retrieve_with_videos("plants")

    assert documents[0].title == "Just a title and content"
    assert documents[0].content == "Just a title and content"
    assert documents[0].id.startswith("web:")
    assert documents[0].metadata.get("source") == "web_search"


async def test_t19e_fetch_documents_passes_course_id_filter() -> None:
    captured: list[object] = []

    class FilterCaptureRepository(IDataRepository):
        async def find_documents(self, query: str, limit: int = 10, *, filters=None) -> list[DocumentHit]:
            captured.append(filters)
            return []

    repo = FilterCaptureRepository()
    workflow = DocumentVideoWorkflow(repo, FakeVideoClient([]))

    await workflow.fetch_documents("arrays", 5, course_id="javascript")

    assert captured[0] is not None
    assert captured[0].course_id == "javascript"  # type: ignore[union-attr]
    assert captured[0].tenant_id is None  # type: ignore[union-attr]
