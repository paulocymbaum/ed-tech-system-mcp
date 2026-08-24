"""Port-adapter cache serialization with pruning, compression, and size guards.

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

from mcp_server.domain.schemas import VideoResult

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


def payload_within_cache_limit(payload: bytes) -> bool:
    """Return whether a serialized payload is small enough to store in cache."""
    return len(payload) <= MAX_CACHE_PAYLOAD_BYTES
