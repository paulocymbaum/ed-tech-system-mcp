#!/usr/bin/env python3
"""Minimal document ingest CLI — chunk, embed passages, upsert to vector store."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

from mcp_server.env_bootstrap import bootstrap_environment
from mcp_server.settings import load_settings
from mcp_server.wiring import (
    build_chunking_strategy,
    build_embedding_provider,
    build_vector_index_writer,
    create_cache_store,
)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index a text document into the configured vector store (Chroma or Supabase).",
    )
    parser.add_argument("--document-id", required=True, help="Parent document UUID")
    parser.add_argument("--title", required=True, help="Document title")
    parser.add_argument("--file", required=True, type=Path, help="Path to plain-text/markdown file")
    parser.add_argument("--language", default=None, help="ISO 639-1 language code for FTS")
    parser.add_argument("--course-id", default=None, help="Optional course filter id")
    return parser.parse_args()


async def _ingest(args: argparse.Namespace) -> None:
    settings = load_settings()
    cache_store = create_cache_store(settings)
    chunking = build_chunking_strategy(settings)
    embedder = build_embedding_provider(settings, cache_store)
    writer = build_vector_index_writer(settings)

    text = args.file.read_text(encoding="utf-8")
    document_id = str(uuid.UUID(args.document_id))
    content_hash = _content_hash(text)
    metadata: dict[str, str] = {"title": args.title}
    if args.course_id:
        metadata["course_id"] = args.course_id

    upsert_document = getattr(writer, "upsert_document", None)
    if callable(upsert_document):
        await upsert_document(
            document_id=document_id,
            title=args.title,
            content=text,
            content_hash=content_hash,
            course_id=args.course_id,
            language=args.language,
        )

    chunks = chunking.chunk(
        text,
        document_id=document_id,
        language=args.language,
        metadata=metadata,
    )
    if not chunks:
        print("No chunks produced; nothing to index.", file=sys.stderr)
        return

    embeddings = await embedder.embed_passages([chunk.content for chunk in chunks])
    if embeddings and len(embeddings[0]) != embedder.dimensions:
        msg = (
            f"Embedding dimension mismatch: expected {embedder.dimensions}, "
            f"got {len(embeddings[0])}"
        )
        raise ValueError(msg)

    await writer.upsert_chunks(chunks, embeddings)
    print(f"Indexed {len(chunks)} chunks for document {document_id}")


def main() -> None:
    bootstrap_environment()
    args = _parse_args()
    asyncio.run(_ingest(args))


if __name__ == "__main__":
    main()
