"""LangChain text splitter behind IChunkingStrategy."""

from __future__ import annotations

import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter

from mcp_server.domain.interfaces import IChunkingStrategy
from mcp_server.domain.schemas import TextChunk


def _content_hash(content: str) -> str:
    normalized = content.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class LangChainChunkingAdapter(IChunkingStrategy):
    """Split documents with recursive character chunking (tiktoken-sized)."""

    def __init__(
        self,
        *,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
    ) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap

    def chunk(
        self,
        text: str,
        *,
        document_id: str,
        language: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        base_metadata = dict(metadata or {})
        pieces = self._splitter.split_text(text)
        chunks: list[TextChunk] = []
        for index, piece in enumerate(pieces):
            chunks.append(
                TextChunk(
                    document_id=document_id,
                    content=piece,
                    content_hash=_content_hash(piece),
                    language=language,
                    metadata=base_metadata,
                    chunk_index=index,
                )
            )
        return chunks
