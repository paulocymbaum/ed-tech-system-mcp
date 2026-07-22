# Implementation 7: Infrastructure trivial cleanup test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST7.md](./TEST7.md)
**Status:** done

## Summary

Homologated BL-026, BL-025, and BL-024 by mapping existing cache/LLM tests to TEST7 catalog IDs. Added one gap test (INF24b) for the documented sync `_generate` cache bypass.

## Checklist

- [x] **1.** Map BL-026 — INF26 → `test_c09_build_cache_rule_set_applies_ttl_override` (`test_cache.py`)
- [x] **2.** Map BL-025 — INF25 → no test (deletion only; investigation confirms zero importers)
- [x] **3.** Map BL-024 async — INF24a → `test_llm04_cached_chat_model_hits_cache_on_second_ainvoke` (`test_llm.py`)
- [x] **4.** Map BL-024 observability — INF24c → `test_c24_cached_llm_logs_hit_on_second_call` (`test_cache.py`)
- [x] **5.** Map BL-024 wiring — INF24d → `test_llm07_build_chat_model_wraps_with_cache_when_enabled` (`test_llm.py`)
- [x] **6.** Add INF24b — `test_llm04b_cached_chat_model_sync_generate_bypasses_cache` in `test_llm.py`
- [x] **7.** Run `uv sync --frozen`
- [x] **8.** Run `uv run ruff check src/ tests/`
- [x] **9.** Run `uv run pytest -v`
- [x] **10.** Write `HOMOLOGATION.md` coverage matrix for TEST7
- [x] **11.** Set TEST7.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_cache.py` | INF26, INF24c | mapped existing |
| `tests/test_llm.py` | INF24a, INF24b, INF24d | mapped existing + added INF24b |

### Verification

```bash
uv sync --frozen
uv run ruff check src/ tests/
uv run pytest -v
```

### Verification results

```text
uv run ruff check src/ tests/  → All checks passed!
uv run pytest -v               → 103 passed, 1 warning in 2.97s
```
