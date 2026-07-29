"""Port-adapter cache serialization with pruning, compression, and size guards.

Pruned fields (BL-015):
- ``DocumentHit.content`` — truncated to ``DOCUMENT_CONTENT_MAX_LEN`` characters plus
  ``"..."`` when longer (aligned with MCP ``document_hit_to_summary`` snippet length).
- ``DocumentHit.metadata`` — omitted from cache payloads; deserializes as empty dict.

``VideoResult`` and web-search snippet lists are stored in full (small or gzip-compressed).

Envelope format (new writes):
- ``b"\\x02j"`` + UTF-8 JSON body (uncompressed)
- ``b"\\x02z"`` + gzip-compressed UTF-8 JSON body when body length exceeds
  ``COMPRESS_THRESHOLD_BYTES``

Legacy entries without the ``\\x02`` prefix remain readable (raw JSON array/object).
"""

from __future__ import annotations

import gzip
import json

from mcp_server.domain.schemas import ChunkHit, DocumentHit, VideoResult

DOCUMENT_CONTENT_MAX_LEN = 200
COMPRESS_THRESHOLD_BYTES = 1024
MAX_CACHE_PAYLOAD_BYTES = 512 * 1024

_ENVELOPE_VERSION = b"\x02"
_JSON_MARKER = b"j"
_GZIP_MARKER = b"z"


def _encode_port_payload(json_bytes: bytes) -> bytes:
    if len(json_bytes) > COMPRESS_THRESHOLD_BYTES:
        body = gzip.compress(json_bytes)
        return _ENVELOPE_VERSION + _GZIP_MARKER + body
    return _ENVELOPE_VERSION + _JSON_MARKER + json_bytes


def _decode_port_payload(payload: bytes) -> bytes:
    if payload.startswith(_ENVELOPE_VERSION) and len(payload) >= 2:
        marker = payload[1:2]
        body = payload[2:]
        if marker == _GZIP_MARKER:
            return gzip.decompress(body)
        if marker == _JSON_MARKER:
            return body
    return payload


def _document_hit_for_cache(hit: DocumentHit) -> dict[str, object]:
    content = hit.content
    if len(content) > DOCUMENT_CONTENT_MAX_LEN:
        content = f"{content[:DOCUMENT_CONTENT_MAX_LEN]}..."
    return {"id": hit.id, "title": hit.title, "content": content}


def serialize_documents(documents: list[DocumentHit]) -> bytes:
    """Serialize document hits for cache storage with pruned fields."""
    raw = [_document_hit_for_cache(document) for document in documents]
    json_bytes = json.dumps(raw).encode("utf-8")
    return _encode_port_payload(json_bytes)


def deserialize_documents(payload: bytes) -> list[DocumentHit]:
    """Deserialize cached document hits, including legacy unprefixed JSON."""
    json_bytes = _decode_port_payload(payload)
    raw = json.loads(json_bytes.decode("utf-8"))
    return [DocumentHit.model_validate(item) for item in raw]


def serialize_videos(videos: list[VideoResult]) -> bytes:
    """Serialize video results for cache storage."""
    json_bytes = json.dumps([video.model_dump() for video in videos]).encode("utf-8")
    return _encode_port_payload(json_bytes)


def deserialize_videos(payload: bytes) -> list[VideoResult]:
    """Deserialize cached video results, including legacy unprefixed JSON."""
    json_bytes = _decode_port_payload(payload)
    raw = json.loads(json_bytes.decode("utf-8"))
    return [VideoResult.model_validate(item) for item in raw]


def serialize_snippets(snippets: list[str]) -> bytes:
    """Serialize web-search snippets for cache storage."""
    json_bytes = json.dumps(snippets).encode("utf-8")
    return _encode_port_payload(json_bytes)


def deserialize_snippets(payload: bytes) -> list[str]:
    """Deserialize cached snippets, including legacy unprefixed JSON."""
    json_bytes = _decode_port_payload(payload)
    raw = json.loads(json_bytes.decode("utf-8"))
    return [str(item) for item in raw]


def serialize_chunks(chunks: list[ChunkHit]) -> bytes:
    """Serialize chunk hits for cache storage."""
    json_bytes = json.dumps([chunk.model_dump() for chunk in chunks]).encode("utf-8")
    return _encode_port_payload(json_bytes)


def deserialize_chunks(payload: bytes) -> list[ChunkHit]:
    """Deserialize cached chunk hits, including legacy unprefixed JSON."""
    json_bytes = _decode_port_payload(payload)
    raw = json.loads(json_bytes.decode("utf-8"))
    return [ChunkHit.model_validate(item) for item in raw]


def payload_within_cache_limit(payload: bytes) -> bool:
    """Return whether a serialized payload is small enough to store in cache."""
    return len(payload) <= MAX_CACHE_PAYLOAD_BYTES
