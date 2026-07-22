# Implementation 5: Composition root cache wiring test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST5.md](./TEST5.md)
**Status:** done

## Summary

Homologate increment 3 (BL-002, BL-003, BL-008, BL-012, BL-018) by mapping existing tests to TEST5 catalog IDs. Tests were delivered with entrypoint IMPLEMENTATION3; this pass verifies coverage, fixes ruff import order in `test_cache.py`, and produces HOMOLOGATION evidence.

## Checklist

- [x] **1.** Map C21 — single `create_cache_store` per boot (`test_cache.py`)
- [x] **2.** Map C22 — `McpToolCacheEnvelope` round-trip (`test_cache.py`)
- [x] **3.** Map C23 — adapter cache hit logging (`test_cache.py`)
- [x] **4.** Map C24 — LLM cache hit logging (`test_cache.py`)
- [x] **5.** Map T21 — `health_check` tool cache integration (`test_interface_tools.py`)
- [x] **6.** Map T20 — `health_check` without cache runtime (`test_interface_tools.py`)
- [x] **7.** Map E01 — `main()` passes settings to runtime init (`test_entrypoint.py`)
- [x] **8.** Map LLM07 / LLM07b — builder cache guard and wrap (`test_llm.py`)
- [x] **9.** Map C18 / C08 — Redis degradation and disabled cache (`test_cache.py`)
- [x] **10.** Manual DOC01 — verify `ENVIRONMENT_SETUP.md` production cache section
- [x] **11.** Fix `tests/test_cache.py` import order (ruff I001)
- [x] **12.** Run `uv run ruff check src/ tests/`
- [x] **13.** Run `uv run pytest -v`
- [x] **14.** Write `HOMOLOGATION.md` coverage matrix for TEST5
- [x] **15.** Set TEST5.md → approved, this file → done

## Task details

### Test modules (no new files)

| Module | Catalog IDs |
| :--- | :--- |
| `tests/test_cache.py` | C08, C18, C21, C22, C23, C24 |
| `tests/test_interface_tools.py` | T20, T21 |
| `tests/test_entrypoint.py` | E01 |
| `tests/test_llm.py` | LLM07, LLM07b |

### Verification

```bash
uv sync --frozen
uv run ruff check src/ tests/
uv run pytest -v
```
