# Implementation 10: Cache serialization + stampede protection test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST10.md](./TEST10.md)
**Status:** done

## Summary

Mapped infrastructure increment 4 deliverables (BL-015, BL-016) to nine pytest functions in `tests/test_cache.py`. C29–C34 and updated C03 were delivered during IMPLEMENTATION4 and CODE_REVIEW4 remediation. C35 (video client stampede) was added to close the BL-016 gap for `CachedVideoSearchClient`.

## Checklist

- [x] **1.** Map BL-015 document pruning — C29 → `test_c29_document_cache_prunes_content_and_metadata`
- [x] **2.** Map BL-015 gzip envelope — C30 → `test_c30_large_snippet_list_uses_gzip_envelope`
- [x] **3.** Map BL-015 oversize skip-set — C31 → `test_c31_oversize_payload_skips_set_but_returns_result`
- [x] **4.** Map BL-015 legacy JSON — C33 → `test_c33_legacy_unprefixed_document_payload_deserializes`
- [x] **5.** Map BL-016 repository stampede — C32 → `test_c32_parallel_misses_invoke_inner_port_once`
- [x] **6.** Map BL-016 search stampede — C34 → `test_c34_cached_search_client_parallel_misses_invoke_inner_once`
- [x] **7.** Implement BL-016 video stampede — C35 → `test_c35_cached_video_client_parallel_misses_invoke_inner_once`
- [x] **8.** Map BL-016 double-check regression — C03 → `test_c03_cached_repository_hits_cache_on_second_call`
- [x] **9.** Run `uv sync --frozen`
- [x] **10.** Run `uv run ruff check src/ tests/`
- [x] **11.** Run `uv run mypy src/`
- [x] **12.** Run `uv run pytest -v`
- [x] **13.** Write `HOMOLOGATION.md` coverage matrix for TEST10
- [x] **14.** Set TEST10.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_cache.py` | C03, C29–C35 | mapped C03, C29–C34 existing; added C35 + `SlowCountingVideoClient` fake |

### Verification results

```text
uv run ruff check src/ tests/  → All checks passed!
uv run mypy src/               → Success: no issues found in 42 source files
uv run pytest -v               → 120 passed, 1 warning in 3.06s
```
