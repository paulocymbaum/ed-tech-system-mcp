# Investigation 4: Cache serialization + stampede protection (BL-015, BL-016)

**Date:** 2026-07-21
**Layer:** infrastructure (primary); domain (serialization contract)
**Status:** approved

## User request

Batch 4 — cache hardening backlog items in one increment:

- **BL-015** — Optimize cache serialization: prune large fields before `model_dump()`, gzip large payloads, cap max cached payload with uncached fallback, extract shared serialization helpers, update `tests/test_cache.py`.
- **BL-016** — Cache-aside stampede protection: per-key `asyncio.Lock` / singleflight in shared helper, apply to all three cached port adapters, concurrent miss test (N parallel → 1 inner call), bounded lock map with documented cleanup.

Constraints: stdlib gzip only; preserve backward compatibility for legacy cache entries or versioned envelope; do not change `cached_llm.py` unless minimal shared helper requires it; do not edit `backlog/BACKLOG.md`.

## Architecture alignment

- **Layers touched:** infrastructure (`cache_serialization.py`, `cache_aside.py`, `cached_adapters.py`), tests
- **Patterns applied:** Infrastructure serialization at adapter boundary; shared cache-aside helper (D03 debt resolved alongside BL-016); versioned payload envelope for forward-compatible compression; graceful degradation (skip `set` on oversize payload)
- **Anti-patterns avoided:** No Redis/domain imports in serialization helpers; no stampede locks in domain; no changes to `cached_llm.py` scope; no `os.environ` outside entrypoint

## Current state

| Asset | Status |
| :--- | :--- |
| `cached_adapters.py` | Full `model_dump()` for `DocumentHit`/`VideoResult`; raw JSON bytes; duplicated cache-aside miss path (get → miss → inner → set) |
| `cache_envelope.py` | MCP tool envelope only (`McpToolCacheEnvelope`); unrelated to port adapters |
| `DocumentHit` | `id`, `title`, `content` (large), `metadata` — workflows use `title` only; MCP maps to 200-char snippet via `document_hit_to_summary` |
| `VideoResult` | Small scalar fields; no pruning needed |
| Web search cache | `list[str]` snippets; compression sufficient |
| Stampede | PERFORMANCE_AUDIT1 P06 — concurrent misses all call inner port |
| `tests/test_cache.py` | C01–C28 cover keys, hit/miss, observability; no serialization pruning, compression, size cap, or stampede tests |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| `DocumentHit.content`/`metadata` bloat Redis (BL-015) | infrastructure | high |
| No gzip for large JSON payloads (BL-015) | infrastructure | high |
| No max payload guard before `set` (BL-015) | infrastructure | high |
| Duplicated cache-aside miss logic (BL-016, D03) | infrastructure | high |
| No per-key singleflight (BL-016) | infrastructure | high |
| Legacy cache entries without envelope prefix | infrastructure | medium |

## Minimal increment

Add `cache_serialization.py` with versioned port-cache envelope (`\x02` + `j`|`z` + body), document pruning (truncate `content` to 200 chars + `...`, omit `metadata`), gzip when JSON body exceeds 1 KiB, and skip `cache.set` when final payload exceeds 512 KiB (still return live result). Deserialize accepts legacy raw JSON arrays for backward compatibility.

Add `cache_aside.py` with `CacheAsideCoordinator` (per-key `asyncio.Lock`, pop lock entry when idle, clear map when size exceeds 1024 keys) and `run_cache_aside()` helper (fast-path hit outside lock; double-check inside singleflight before inner call).

Refactor `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient` to use both modules; keep `port_call_span` and observability hooks unchanged.

### Scope (in)

- `cache_serialization.py` — prune/serialize/deserialize for documents, videos, snippets; constants documented in module docstring
- `cache_aside.py` — singleflight coordinator + `run_cache_aside`
- `cached_adapters.py` — delegate to helpers
- Tests C29–C33 in `tests/test_cache.py`
- `ruff`, `mypy`, `pytest`

### Scope (out / deferred)

- `cached_llm.py` serialization/compression (separate payload shape; out of scope unless shared constants imported)
- `McpToolInteractionCache` stampede protection (not in BL-016 acceptance list)
- Redis connection pooling (separate backlog)
- Domain `DocumentHit.to_cache_dict()` — pruning stays infrastructure-side to avoid domain knowing cache limits

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `infrastructure/cache_serialization.py` | create | Centralize prune, envelope, gzip, size cap |
| `infrastructure/cache_aside.py` | create | Singleflight + shared miss path |
| `infrastructure/cached_adapters.py` | modify | Use new helpers; remove inline serialize/deserialize |
| `tests/test_cache.py` | modify | Pruning, compression, size cap, stampede, legacy compat |

## Dependencies & environment

- Runtime deps: none (stdlib `gzip`, `json`)
- Dev deps: existing pytest/pytest-asyncio
- Secrets / env vars: none
- Commands: `uv sync --frozen`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Pruned `content` on cache hit:** Callers receive truncated body (≤203 chars) matching MCP snippet exposure; full content only on first uncached fetch. Acceptable per BL-015 and `document_hit_to_summary` contract.
- **Legacy entries:** Unprefixed JSON still deserializes; new writes use `\x02` envelope.
- **Lock map growth:** Bounded via post-release pop + full clear at 1024 entries; documented in `cache_aside.py`.

## Handoff to implementation

`IMPLEMENTATION4.md` should checklist: create serialization + aside modules, refactor adapters, add five tests, run quality gates, mark investigation approved and implementation done.
