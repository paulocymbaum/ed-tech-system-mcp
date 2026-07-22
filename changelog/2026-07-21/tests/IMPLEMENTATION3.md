# Implementation 3: Operational config and model registry test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST3.md](./TEST3.md)
**Status:** done

## Summary

Map existing operational-config and model-registry tests to TEST3 catalog IDs (O01–O06, E01, L01–L04). Add gap tests O08–O12 and L05 from CODE_REVIEW2. No new test modules — extend `test_operational_config.py` and `test_llm_models.py`.

## Checklist

- [x] **1.** Rename existing `test_operational_config.py` functions to `test_oNN_*` catalog IDs (O01–O06)
- [x] **2.** Rename `test_main_startup_loads_operational_config_before_mcp_server` → `test_e01_*`
- [x] **3.** Rename existing `test_llm_models.py` functions to `test_lNN_*` (L01–L04)
- [x] **4.** Implement O08 (zero retries allowed)
- [x] **5.** Implement O09 (`build_workflow_execution_config` field mapping)
- [x] **6.** Implement O10 (`default_config_path` resolves to repo root)
- [x] **7.** Implement O11 (missing file raises)
- [x] **8.** Implement O12 (missing keys raises ValidationError)
- [x] **9.** Implement L05 (unique model IDs)
- [x] **10.** Run `uv sync --frozen`
- [x] **11.** Run `uv run ruff check src/ tests/`
- [x] **12.** Run `uv run pytest -v`
- [x] **13.** Write `HOMOLOGATION.md` coverage matrix for TEST3
- [x] **14.** Set TEST3.md → approved, this file → done

## Task details

### 1–3. Rename existing tests

Align function names with TEST3 catalog IDs without changing behavior.

### 4–9. New gap tests

Use tmp paths for file-error cases. O09 asserts `workflow_timeout_seconds` / `agent_node_timeout_seconds` mapping from operational field names. L05 collects `id` values and asserts uniqueness.

### Verification

```bash
uv sync --frozen
uv run ruff check src/ tests/
uv run pytest -v
```
