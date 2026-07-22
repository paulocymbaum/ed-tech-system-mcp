# Implementation 4: Cache serialization + stampede protection (BL-015, BL-016)

**Date:** 2026-07-21
**Layer:** infrastructure
**Investigation:** [INVESTIGATION4.md](./INVESTIGATION4.md)
**Status:** done

## Summary

Added `cache_serialization.py` (document field pruning, `\x02j`/`\x02z` versioned envelope, gzip above 1 KiB, 512 KiB max payload guard with skip-set fallback) and `cache_aside.py` (per-key singleflight via `CacheAsideCoordinator`, shared `run_cache_aside()`). Refactored all three cached port adapters to use both modules while preserving `port_call_span` and observability. Tests C29–C34 cover pruning, compression, oversize skip, stampede coalescing (repository + search client), and legacy JSON compat.

## Checklist

- [x] **1.** Create `src/mcp_server/infrastructure/cache_serialization.py`
- [x] **2.** Create `src/mcp_server/infrastructure/cache_aside.py`
- [x] **3.** Refactor `cached_adapters.py` to use serialization + cache-aside helpers
- [x] **4.** Add tests C29–C33 in `tests/test_cache.py`
- [x] **5.** Run `uv run ruff check src/` and fix issues
- [x] **6.** Run `uv run mypy src/`
- [x] **7.** Run `uv run pytest`
- [x] **8.** Update investigation status; set implementation status to `done`

## Task details

### 1. `cache_serialization.py`

- **File(s):** `src/mcp_server/infrastructure/cache_serialization.py`
- **Done when:** Module docstring documents pruned fields; `serialize_*` / `deserialize_*` for documents, videos, snippets; `\x02j`/`\x02z` envelope; legacy JSON fallback; `MAX_CACHE_PAYLOAD_BYTES` guard helper

### 2. `cache_aside.py`

- **File(s):** `src/mcp_server/infrastructure/cache_aside.py`
- **Done when:** `CacheAsideCoordinator` with bounded lock map; `run_cache_aside()` implements fast-path hit, singleflight miss, double-check, conditional set

### 3. `cached_adapters.py`

- **Done when:** Inline serialize/deserialize removed; all three adapters call `run_cache_aside`

### 4. Tests

- **C29** — Document cache prunes long `content` and omits `metadata`
- **C30** — Large snippet list stored with gzip marker (`\x02z`)
- **C31** — Oversize payload skips `set`, still returns result
- **C32** — N parallel misses on same key → 1 inner call (`CachedDataRepository`)
- **C33** — Legacy unprefixed JSON deserializes
- **C34** — N parallel misses on same key → 1 inner call (`CachedSearchClient`)

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Verification

```text
uv run ruff check src/   → All checks passed
uv run mypy src/         → Success: no issues found in 42 source files
uv run pytest            → 119 passed (post-remediation C34)
```

## Deviations

- `test_c03` updated: first miss path performs double-check `get` inside singleflight (3 total gets for miss+hit sequence).
- `cached_llm.py` unchanged per scope constraint.

## Remediation (Stage 3 — CODE_REVIEW4)

**Status:** done

### Checklist

- [x] **R1.** Add C34 — `CachedSearchClient` parallel miss coalescing via shared `run_cache_aside`
- [x] **R2.** Document deferred lock-map clear trade-off (no code change)
- [x] **R3.** Defer uncommitted delivery to master (procedural)
- [x] **R4.** Run `uv run ruff check src/`
- [x] **R5.** Run `uv run mypy src/`
- [x] **R6.** Run `uv run pytest`

### R1 — Stampede test scope (fixed)

Added `test_c34_cached_search_client_parallel_misses_invoke_inner_once`: 8 concurrent `search` calls on a cold key with `SlowCountingSearchClient` assert `inner.calls == 1` and `cache.set_calls == 1`. Exercises the same `run_cache_aside` singleflight path as C32 through a second adapter type.

### R2 — Lock-map clear vs singleflight (deferred)

`CacheAsideCoordinator` clears the entire lock map when `len(self._locks) >= max_locks` (1024). **Rationale:** unbounded per-key locks would grow with cache-key cardinality under load; clearing caps memory. In-flight holders retain their `asyncio.Lock` objects until release, so correctness is preserved for active keys. A concurrent request for a key whose lock entry was evicted may allocate a second lock and briefly bypass coalescing until the first holder finishes — acceptable at current scale (low concurrent key fan-out per process). Monitoring under high key cardinality is the operational mitigation; no code change in this increment.

### R3 — Uncommitted delivery (deferred)

Working-tree changes remain uncommitted; master agent handles commit/PR.
