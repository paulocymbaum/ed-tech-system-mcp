# Implementation 9: Port-call timing spans + per-tool latency test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST9.md](./TEST9.md)
**Status:** done

## Summary

Mapped infrastructure increment 3 deliverables (BL-017, BL-019) to six existing pytest functions delivered during IMPLEMENTATION3 and CODE_REVIEW3 remediation (C27, C28, T28). No new tests required — all catalog cases were implemented during the feature increment.

## Checklist

- [x] **1.** Map BL-017 disabled path — C25 → `test_c25_port_call_span_logs_disabled_on_cache_bypass` (`test_cache.py`)
- [x] **2.** Map BL-017 find_documents miss/hit — C26 → `test_c26_port_call_span_logs_miss_then_hit` (`test_cache.py`)
- [x] **3.** Map BL-017 web.search miss/hit — C27 → `test_c27_port_call_span_logs_miss_then_hit_for_web_search` (`test_cache.py`)
- [x] **4.** Map BL-017 youtube.search_videos miss/hit — C28 → `test_c28_port_call_span_logs_miss_then_hit_for_youtube_search_videos` (`test_cache.py`)
- [x] **5.** Map BL-019 success timing — T27 → `test_t27_health_check_logs_tool_timing` (`test_interface_tools.py`)
- [x] **6.** Map BL-019 error timing — T28 → `test_t28_cached_tool_invoke_logs_error_outcome` (`test_interface_tools.py`)
- [x] **7.** Run `uv sync --frozen`
- [x] **8.** Run `uv run ruff check src/ tests/`
- [x] **9.** Run `uv run pytest -v`
- [x] **10.** Write `HOMOLOGATION.md` coverage matrix for TEST9
- [x] **11.** Set TEST9.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_cache.py` | C25, C26, C27, C28 | mapped existing (IMPLEMENTATION3 + remediation) |
| `tests/test_interface_tools.py` | T27, T28 | mapped existing (IMPLEMENTATION3 + remediation) |

### Verification results

```text
uv run ruff check src/ tests/  → All checks passed!
uv run pytest -v               → 113 passed, 1 warning in 3.02s
```
