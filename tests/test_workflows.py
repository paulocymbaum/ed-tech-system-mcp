"""Application workflow contract tests (T15–T19)."""

import asyncio

from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.interfaces import IDataRepository, IVideoSearchClient
from mcp_server.domain.schemas import DocumentHit, VideoResult


class FakeRepository(IDataRepository):
    def __init__(self, documents: list[DocumentHit]) -> None:
        self._documents = documents
        self.last_query: str | None = None
        self.last_limit: int | None = None
        self.in_flight = 0
        self.max_in_flight = 0

    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
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


async def test_t19b_parallel_io_when_no_documents() -> None:
    class ParallelTracker:
        def __init__(self) -> None:
            self.doc_started = False
            self.doc_finished = False
            self.video_started_before_doc_finished = False

    tracker = ParallelTracker()

    class TrackingRepository(IDataRepository):
        async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
            tracker.doc_started = True
            await asyncio.sleep(0.05)
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
            if tracker.doc_started and not tracker.doc_finished:
                tracker.video_started_before_doc_finished = True
            return []

    workflow = DocumentVideoWorkflow(TrackingRepository(), TrackingVideoClient())

    await workflow.retrieve_with_videos("plants")

    assert tracker.video_started_before_doc_finished is True


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
