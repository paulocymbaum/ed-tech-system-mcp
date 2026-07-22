# Code Review 4: Cache serialization + stampede protection (BL-015, BL-016)

**Date:** 2026-07-21
**Layer:** infrastructure
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION4.md](./INVESTIGATION4.md)
- [IMPLEMENTATION4.md](./IMPLEMENTATION4.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| — | **No commits** — increment 4 exists only as unstaged/untracked working-tree changes on `testbranch` |

**Working-tree files in scope (infrastructure increment 4):**

| Path | Change |
| :--- | :--- |
| `src/mcp_server/infrastructure/cache_serialization.py` | new (untracked) |
| `src/mcp_server/infrastructure/cache_aside.py` | new (untracked) |
| `src/mcp_server/infrastructure/cached_adapters.py` | modified — delegates to serialization + `run_cache_aside` |
| `tests/test_cache.py` | modified — C29–C33; `test_c03` get-count assertion updated |
| `changelog/2026-07-21/infrastructure/IMPLEMENTATION4.md` | new (untracked) |

## Summary

INVESTIGATION4 and IMPLEMENTATION4 are implemented on the working tree. `cache_serialization.py` centralizes document field pruning (200-char content cap, metadata omitted), `\x02j`/`\x02z` versioned envelopes, gzip above 1 KiB, and a 512 KiB max-payload guard that skips `set` while returning the live loader result. `cache_aside.py` provides per-key singleflight via `CacheAsideCoordinator` and a shared `run_cache_aside()` fast-path hit / double-check miss path. All three `Cached*` port adapters delegate to both helpers while preserving `port_call_span` and DEBUG cache observability from increment 3. Tests C29–C33 cover pruning, gzip envelope, oversize skip-set, parallel miss coalescing, and legacy JSON compat. All quality gates pass (118 tests). Verdict is **approve with nits** — BL-015/BL-016 acceptance criteria are met and layer boundaries respected, but the increment is uncommitted and stampede coverage exercises only one adapter.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION4 | Scope delivered: `cache_serialization.py`, `cache_aside.py`, refactored `cached_adapters.py`, C29–C33, quality gates. Deferred items respected (`cached_llm.py` unchanged, no `McpToolInteractionCache` stampede, no domain `to_cache_dict()`, no backlog edits). |
| IMPLEMENTATION4 | All 8 checklist items checked; status `done` matches code on disk. Documented `test_c03` deviation (3 gets on miss+hit due to double-check inside singleflight). |
| ARCHITECTURE.md | File tree does not yet list `cache_serialization.py` or `cache_aside.py` — doc drift only; no layer-rule violation. |
| ENVIRONMENT_SETUP.md | Stdlib `gzip`/`json` only; no new env vars; verification commands match project CI gate. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `cache_serialization.py` — prune, envelope, gzip, size cap, legacy fallback | Module with `DOCUMENT_CONTENT_MAX_LEN=200`, `COMPRESS_THRESHOLD_BYTES=1024`, `MAX_CACHE_PAYLOAD_BYTES=512KiB`, `serialize_*`/`deserialize_*` for documents/videos/snippets | match |
| `cache_aside.py` — `CacheAsideCoordinator`, `run_cache_aside()` | Per-key `asyncio.Lock`, pop on idle, clear at 1024 keys; fast-path hit, singleflight double-check, conditional `set` | match |
| Refactor `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient` | All three call `run_cache_aside` with typed serialize/deserialize pairs | match |
| Remove inline serialize/deserialize from `cached_adapters.py` | Inline helpers removed; imports from `cache_serialization` | match |
| Preserve `port_call_span` + observability hooks | Adapters still wrap with `port_call_span`; `run_cache_aside` calls `record_cache_hit`/`record_cache_miss` and sets `span.cache` | match |
| **C29** — prune content, omit metadata | `test_c29_document_cache_prunes_content_and_metadata` | match |
| **C30** — gzip marker `\x02z` for large snippets | `test_c30_large_snippet_list_uses_gzip_envelope` | match |
| **C31** — oversize skips `set`, returns result | `test_c31_oversize_payload_skips_set_but_returns_result` (monkeypatched 32-byte cap) | match |
| **C32** — N parallel misses → 1 inner call | `test_c32_parallel_misses_invoke_inner_port_once` (8 concurrent, `CachedDataRepository`) | match |
| **C33** — legacy unprefixed JSON | `test_c33_legacy_unprefixed_document_payload_deserializes` | match |
| Scope out: `cached_llm.py` | Unchanged; no imports from new modules | match |
| Scope out: `McpToolInteractionCache` stampede | Not implemented | match |
| Run `ruff`, `mypy`, `pytest` | All pass (118 tests, 42 mypy files) | match |

## Layer review (infrastructure)

### Files reviewed

- `src/mcp_server/infrastructure/cache_serialization.py` — pruning, `\x02` envelope encode/decode, gzip threshold, `payload_within_cache_limit`
- `src/mcp_server/infrastructure/cache_aside.py` — `CacheAsideCoordinator.singleflight`, module-level `_coordinator`, generic `run_cache_aside[T]`
- `src/mcp_server/infrastructure/cached_adapters.py` — three adapters delegate serialization and cache-aside; disabled-rule pass-through unchanged
- `tests/test_cache.py` — C29–C33 plus updated `test_c03` (`cache.get_calls == 3`)

### Architecture & patterns

- Serialization helpers use stdlib `gzip`/`json` only; domain import limited to entity types (`DocumentHit`, `VideoResult`) for prune/validate — no Redis, MCP, or `os.environ`.
- Pruning stays infrastructure-side per investigation; aligns with `document_hit_to_summary` 200-char snippet contract in `interface/validation.py`.
- `run_cache_aside` implements correct cache-aside ordering: fast-path hit outside lock → singleflight → double-check get → loader → size-guarded set → return live value (not re-deserialized), so oversize and pruned-on-write paths return full loader output on first fetch.
- Legacy unprefixed JSON arrays deserialize via `_decode_port_payload` passthrough; new writes use versioned envelope.
- Shared `_coordinator` singleton is safe because `build_cache_key` namespaces keys per operation and arguments.
- `cached_llm.py` untouched per scope constraint.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected — helpers are infrastructure-internal; adapters still implement domain ports
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **Uncommitted increment** — `cache_serialization.py`, `cache_aside.py`, adapter refactor, tests, and `IMPLEMENTATION4.md` are working-tree only on `testbranch`; commit before merge so CI and reviewers see a bounded diff.
- **Lock-map clear vs singleflight** — when `len(self._locks) >= max_locks`, `CacheAsideCoordinator` clears the entire map before creating a new lock. In-flight holders retain their `asyncio.Lock` objects, but a concurrent request for the same key may allocate a second lock and bypass coalescing until the first holder releases. Documented in investigation as a bounded-memory trade-off; acceptable at current scale but worth monitoring under high key cardinality.
- **Stampede test scope** — C32 exercises `CachedDataRepository` only. All three adapters share `run_cache_aside`, so behavior is likely identical, but search/video adapters have no dedicated coalescing test.

### Suggestions (consider)

- Update `ARCHITECTURE.md` infrastructure file tree to include `cache_serialization.py` and `cache_aside.py`.
- Add a DEBUG log in `run_cache_aside` when `payload_within_cache_limit` returns false (oversize skip-set) for operability.
- **C29** asserts `payload.startswith(b"\x02")` but not the `\x02j` JSON marker for small document payloads; explicit marker assertion would guard regressions in compression threshold logic.

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (42 files) |
| `uv run pytest` | pass (118 passed) |

## Verdict

**approve with nits**

BL-015 and BL-016 are fully implemented: shared serialization with pruning, compression, and size guard; shared cache-aside with per-key singleflight applied to all three cached port adapters; backward-compatible legacy deserialization; and targeted tests C29–C33. Architecture layer rules hold, quality gates pass, and no secrets risk was found. Nits are process (uncommitted diff) and minor coverage/observability gaps, not functional blockers for the planned increment.
