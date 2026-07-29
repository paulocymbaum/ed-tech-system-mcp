"""Runtime accessors for wired RAG retrieval ports."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from mcp_server.domain.cache import ICacheStore
from mcp_server.domain.interfaces import (
    IChunkingStrategy,
    IEmbeddingProvider,
    IReranker,
    IVectorIndexWriter,
    IVectorRetriever,
)

_embedding_provider: IEmbeddingProvider | None = None
_vector_retriever: IVectorRetriever | None = None
_vector_index_writer: IVectorIndexWriter | None = None
_reranker: IReranker | None = None
_chunking_strategy: IChunkingStrategy | None = None
_lazy_settings: RetrievalSettings | None = None
_lazy_cache_store: ICacheStore | None = None
_embedding_builder: EmbeddingProviderBuilder | None = None
_vector_retriever_builder: VectorRetrieverBuilder | None = None
_vector_index_writer_builder: VectorIndexWriterBuilder | None = None
_reranker_builder: RerankerBuilder | None = None
_chunking_strategy_builder: ChunkingStrategyBuilder | None = None


class RetrievalSettings(Protocol):
    """Settings subset required to build retrieval ports."""


EmbeddingProviderBuilder = Callable[[RetrievalSettings, ICacheStore | None], IEmbeddingProvider]
VectorRetrieverBuilder = Callable[[RetrievalSettings, ICacheStore | None], IVectorRetriever]
VectorIndexWriterBuilder = Callable[[RetrievalSettings, ICacheStore | None], IVectorIndexWriter]
RerankerBuilder = Callable[[RetrievalSettings, ICacheStore | None], IReranker]
ChunkingStrategyBuilder = Callable[[RetrievalSettings, ICacheStore | None], IChunkingStrategy]


def register_embedding_provider_builder(builder: EmbeddingProviderBuilder) -> None:
    global _embedding_builder
    _embedding_builder = builder


def register_vector_retriever_builder(builder: VectorRetrieverBuilder) -> None:
    global _vector_retriever_builder
    _vector_retriever_builder = builder


def register_vector_index_writer_builder(builder: VectorIndexWriterBuilder) -> None:
    global _vector_index_writer_builder
    _vector_index_writer_builder = builder


def register_reranker_builder(builder: RerankerBuilder) -> None:
    global _reranker_builder
    _reranker_builder = builder


def register_chunking_strategy_builder(builder: ChunkingStrategyBuilder) -> None:
    global _chunking_strategy_builder
    _chunking_strategy_builder = builder


def reset_retrieval_client_builders() -> None:
    global _embedding_builder
    global _vector_retriever_builder
    global _vector_index_writer_builder
    global _reranker_builder
    global _chunking_strategy_builder
    _embedding_builder = None
    _vector_retriever_builder = None
    _vector_index_writer_builder = None
    _reranker_builder = None
    _chunking_strategy_builder = None


def configure_lazy_retrieval_clients(
    settings: RetrievalSettings | None,
    cache_store: ICacheStore | None = None,
) -> None:
    global _lazy_settings
    global _lazy_cache_store
    global _embedding_provider
    global _vector_retriever
    global _vector_index_writer
    global _reranker
    global _chunking_strategy
    _lazy_settings = settings
    _lazy_cache_store = cache_store
    _embedding_provider = None
    _vector_retriever = None
    _vector_index_writer = None
    _reranker = None
    _chunking_strategy = None


def set_embedding_provider(provider: IEmbeddingProvider | None) -> None:
    global _embedding_provider
    _embedding_provider = provider


def set_vector_retriever(retriever: IVectorRetriever | None) -> None:
    global _vector_retriever
    _vector_retriever = retriever


def set_vector_index_writer(writer: IVectorIndexWriter | None) -> None:
    global _vector_index_writer
    _vector_index_writer = writer


def set_reranker(reranker: IReranker | None) -> None:
    global _reranker
    _reranker = reranker


def set_chunking_strategy(strategy: IChunkingStrategy | None) -> None:
    global _chunking_strategy
    _chunking_strategy = strategy


def _build_client[T](
    current: T | None,
    builder: Callable[[RetrievalSettings, ICacheStore | None], T] | None,
) -> T | None:
    if current is not None:
        return current
    if _lazy_settings is None or builder is None:
        return None
    return builder(_lazy_settings, _lazy_cache_store)


def get_embedding_provider() -> IEmbeddingProvider | None:
    global _embedding_provider
    built = _build_client(_embedding_provider, _embedding_builder)
    if built is not None:
        _embedding_provider = built
    return _embedding_provider


def get_vector_retriever() -> IVectorRetriever | None:
    global _vector_retriever
    built = _build_client(_vector_retriever, _vector_retriever_builder)
    if built is not None:
        _vector_retriever = built
    return _vector_retriever


def get_vector_index_writer() -> IVectorIndexWriter | None:
    global _vector_index_writer
    built = _build_client(_vector_index_writer, _vector_index_writer_builder)
    if built is not None:
        _vector_index_writer = built
    return _vector_index_writer


def get_reranker() -> IReranker | None:
    global _reranker
    built = _build_client(_reranker, _reranker_builder)
    if built is not None:
        _reranker = built
    return _reranker


def get_chunking_strategy() -> IChunkingStrategy | None:
    global _chunking_strategy
    built = _build_client(_chunking_strategy, _chunking_strategy_builder)
    if built is not None:
        _chunking_strategy = built
    return _chunking_strategy


def reset_retrieval_clients() -> None:
    global _embedding_provider
    global _vector_retriever
    global _vector_index_writer
    global _reranker
    global _chunking_strategy
    global _lazy_settings
    global _lazy_cache_store
    _embedding_provider = None
    _vector_retriever = None
    _vector_index_writer = None
    _reranker = None
    _chunking_strategy = None
    _lazy_settings = None
    _lazy_cache_store = None
