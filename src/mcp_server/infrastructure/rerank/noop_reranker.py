"""Pass-through reranker when RERANK_ENABLED=false."""

from __future__ import annotations

from mcp_server.domain.interfaces import IReranker
from mcp_server.domain.schemas import ChunkHit


class NoOpReranker(IReranker):
    """Return candidates truncated to top_n without re-scoring."""

    @property
    def is_pass_through(self) -> bool:
        return True

    async def rerank(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        _ = query
        return candidates[:top_n]
