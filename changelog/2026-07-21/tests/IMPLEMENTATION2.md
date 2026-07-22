# Implementation 2: Redis cache layer test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST2.md](./TEST2.md)
**Status:** done

## Summary

Extend `tests/test_cache.py` with catalog IDs C01–C19. Rename existing tests to include catalog IDs where missing. Add high-value gaps from CODE_REVIEW1: `CachedSearchClient`, `McpToolInteractionCache`, `NoOpCacheStore`, Redis degradation smoke, `build_mcp_tool_cache`, and `CacheRuleSet.is_enabled`.

## Checklist

- [x] **1.** Map existing `tests/test_cache.py` functions to C01–C11 (rename with `test_cNN_` prefix)
- [x] **2.** Add `CountingSearchClient` fake implementing `ISearchClient`
- [x] **3.** Implement C13–C14 (`CachedSearchClient` hit/miss)
- [x] **4.** Implement C15–C16 (`McpToolInteractionCache` hit/bypass)
- [x] **5.** Implement C17 (`NoOpCacheStore` always miss)
- [x] **6.** Implement C18 (`RedisCacheStore` unreachable host degradation)
- [x] **7.** Implement C12 (`CacheRuleSet.is_enabled`)
- [x] **8.** Implement C19 (`build_mcp_tool_cache` disabled returns None)
- [x] **9.** Run `uv sync --frozen`
- [x] **10.** Run `uv run ruff check src/ tests/`
- [x] **11.** Run `uv run pytest -v`
- [x] **12.** Write `HOMOLOGATION.md` coverage matrix for TEST2
- [x] **13.** Set TEST2.md → approved, this file → done

## Task details

### 1. Rename existing tests

Align function names with TEST2 catalog IDs (`test_c01_…` through `test_c11_…`) without changing behavior.

### 3–6. New cache-aside and degradation tests

Use in-memory `ICacheStore` fakes and counting inner port fakes. For C18, instantiate `RedisCacheStore` with an unreachable host URL; assert `get` returns `None` (no external Redis required).

### Verification

```bash
uv sync --frozen
uv run ruff check src/ tests/
uv run pytest -v
```
