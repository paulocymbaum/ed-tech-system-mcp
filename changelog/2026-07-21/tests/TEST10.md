# Test Inventory 10: Cache serialization + stampede protection (BL-015, BL-016)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [infrastructure/INVESTIGATION4.md](../infrastructure/INVESTIGATION4.md), [infrastructure/IMPLEMENTATION4.md](../infrastructure/IMPLEMENTATION4.md), [infrastructure/CODE_REVIEW4.md](../infrastructure/CODE_REVIEW4.md)

## Scope

Homologate infrastructure increment 4 — Batch 4 cache hardening:

- **BL-015** — `cache_serialization.py`: prune `DocumentHit.content` to 200 chars + `...`, omit `metadata`; `\x02j`/`\x02z` versioned envelope; gzip when JSON body > 1 KiB; skip `cache.set` when payload > 512 KiB (return live loader result); legacy unprefixed JSON deserialize
- **BL-016** — `cache_aside.py`: per-key `asyncio.Lock` singleflight via `run_cache_aside`; applied to `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient`; N parallel misses on same key → 1 inner port call

Layers touched: infrastructure (`cache_serialization.py`, `cache_aside.py`, `cached_adapters.py`), tests (`test_cache.py`). Prior inventories TEST1–TEST9 remain valid.

## Test catalog

### cache_serialization — document pruning (BL-015)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C29 | `test_c29_document_cache_prunes_content_and_metadata` | `cache_serialization.py` docstring; `DOCUMENT_CONTENT_MAX_LEN=200` | `DocumentHit` with content length > 200 and non-empty `metadata` | Serialized round-trip: content truncated to 200 chars + `...`; `metadata` empty dict; envelope starts with `\x02` | Derive expected content from `DOCUMENT_CONTENT_MAX_LEN` constant; assert `deserialize_documents(serialize_documents(...))` fields |

### cache_serialization — compression envelope (BL-015)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C30 | `test_c30_large_snippet_list_uses_gzip_envelope` | `COMPRESS_THRESHOLD_BYTES=1024`; `_GZIP_MARKER=b"z"` | 20 snippets each ~200 chars | Payload starts with `b"\x02z"` | Assert prefix only; threshold from module constant |

### cache_serialization — max payload guard (BL-015)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C31 | `test_c31_oversize_payload_skips_set_but_returns_result` | `payload_within_cache_limit`; `run_cache_aside` skips `set` when over limit | `CachedDataRepository` with `MAX_CACHE_PAYLOAD_BYTES` monkeypatched to 32 | Loader invoked once; `cache.set_calls == 0`; storage empty; result equals live `DocumentHit` list | Monkeypatch constant from contract; use `CountingRepository` fake; assert observable return value and cache side effects |

### cache_serialization — legacy compatibility (BL-015)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C33 | `test_c33_legacy_unprefixed_document_payload_deserializes` | `_decode_port_payload` passthrough for unprefixed JSON | Raw UTF-8 JSON array bytes without `\x02` prefix | `deserialize_documents` returns valid `DocumentHit` list | Build legacy bytes from `json.dumps`; assert `DocumentHit` equality |

### cache_aside — stampede coalescing (BL-016)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C32 | `test_c32_parallel_misses_invoke_inner_port_once` | `run_cache_aside` singleflight on miss | 8 concurrent `find_documents` on cold key; `SlowCountingRepository` | `inner.calls == 1`; `cache.set_calls == 1` | `asyncio.gather` with delay fake; count port invocations only |
| C34 | `test_c34_cached_search_client_parallel_misses_invoke_inner_once` | Same `run_cache_aside` path via `CachedSearchClient` | 8 concurrent `search` on cold key; `SlowCountingSearchClient` | `inner.calls == 1`; `cache.set_calls == 1` | Same pattern as C32 through second adapter type |
| C35 | `test_c35_cached_video_client_parallel_misses_invoke_inner_once` | BL-016 acceptance: all three `Cached*` adapters | 8 concurrent `search_videos` on cold key; `SlowCountingVideoClient` with delay | `inner.calls == 1`; `cache.set_calls == 1` | Same stampede pattern as C32/C34 through `CachedVideoSearchClient` |

### cache_aside — double-check get on miss path (BL-016 regression)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C03 | `test_c03_cached_repository_hits_cache_on_second_call` | `run_cache_aside` fast-path + singleflight double-check | Two sequential `find_documents` with enabled rule | First+second return same docs; `inner.calls == 1`; `cache.get_calls == 3` (1 fast miss + 1 inside lock + 1 hit) | Existing regression from IMPLEMENTATION4; assert get count from documented miss path |

## Deferred (not testable yet)

- **`cached_llm.py` serialization/compression** — out of scope per INVESTIGATION4
- **`McpToolInteractionCache` stampede protection** — not in BL-016 acceptance list
- **`CacheAsideCoordinator` lock-map clear at 1024 keys** — memory bound trade-off documented in IMPLEMENTATION4 remediation; no deterministic unit test without contrived 1024+ key fan-out
- **Small-payload `\x02j` marker explicit assertion** — implied by C29 `\x02` prefix and C30 gzip branch; separate test low value
- **`serialize_videos` / `deserialize_videos` round-trip** — `VideoResult` stored in full; no pruning; covered indirectly by C05/C28 hit paths
- **`BACKLOG.md` updates** — procedural; master handles post-homologation

## Handoff to implementation

[IMPLEMENTATION10.md](./IMPLEMENTATION10.md)
