# Implementation 12: Memoize UI workflow list + config.json defaults test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST12.md](./TEST12.md)
**Status:** done

## Summary

Map BL-023 workflow-list memoization and BL-027 config.json default parity to pytest functions in `tests/test_agent.py` (new/extended), `tests/test_llm.py`, `tests/test_operational_config.py`, and `tests/interface/test_local_ui_api.py`.

## Checklist

- [x] **1.** Map memoization — T-A01 → `test_list_registered_workflows_memoizes_compiled_graph` (existing)
- [x] **2.** Add cache reset rebuild — T-A02 → `test_reset_registered_workflows_cache_rebuilds_on_next_call`
- [x] **3.** Add registered workflow metadata — T-A03 → `test_list_registered_workflows_returns_document_video_discovery_metadata`
- [x] **4.** Map UI list endpoint — T-UI01 → `test_list_workflows_returns_langgraph_metadata` (existing)
- [x] **5.** Map config.json parity — T-WC01 → `test_llm12_default_workflow_execution_config_matches_config_json` (existing)
- [x] **6.** Map field-name mapping — T-WC02 → `test_o09_build_workflow_execution_config_maps_field_names` (existing)
- [x] **7.** Add runtime fallback — T-WC03 → `test_workflow_timeout_seconds_falls_back_to_config_json_defaults`
- [x] **8.** Run `uv sync --frozen`
- [x] **9.** Run `uv run ruff check src/ tests/`
- [x] **10.** Run `uv run mypy src/`
- [x] **11.** Run `uv run pytest -v`
- [x] **12.** Write `HOMOLOGATION.md` coverage matrix for TEST12
- [x] **13.** Set TEST12.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_agent.py` | T-A01–T-A03, T-WC03 | extended (T-A01 existing; added T-A02, T-A03, T-WC03) |
| `tests/interface/test_local_ui_api.py` | T-UI01 | existing |
| `tests/test_llm.py` | T-WC01 | existing |
| `tests/test_operational_config.py` | T-WC02 | existing |

### Verification results

```text
uv run ruff check src/ tests/  → All checks passed!
uv run mypy src/               → Success: no issues found in 44 source files
uv run pytest -v               → 143 passed
```
