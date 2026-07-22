# Implementation 13: REFACTOR2 homologation test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST13.md](./TEST13.md)
**Status:** done

## Summary

Map 11 REFACTOR2 items (RF01, RF03, RF02, RF04, RF07, RF08, RF09, RF10, RF11, RF12, RF21) to existing pytest functions delivered during refactor IMPLEMENTATION1. Add one focused unit test for RF10 (`workflow_state_to_run_response`). All other catalog IDs map to pre-existing tests.

## Checklist

- [x] **1.** RF01 bootstrap — T-RF01a → `test_e06_local_ui_main_bootstraps_application_runtime` (existing)
- [x] **2.** RF01 lifespan — T-RF01b → `test_local_ui_lifespan_bootstraps_application_runtime` (existing)
- [x] **3.** RF03 cancel — T-RF03a–c → `test_t19c`, `test_t19d`, `test_t19b` (existing)
- [x] **4.** RF02 singleflight — T-RF02 → `test_c36_mcp_tool_cache_parallel_misses_invoke_once` (existing)
- [x] **5.** RF07 payload guard — T-RF07 → `test_c37_mcp_tool_cache_skips_oversize_payload` (existing)
- [x] **6.** RF08 LLM singleflight — T-RF08 → `test_llm04c_cached_chat_model_parallel_misses_invoke_inner_once` (existing)
- [x] **7.** RF04 lazy workflow — T-RF04a–b → `test_llm06b`, `test_c21` (existing)
- [x] **8.** RF09 graph memo — T-RF09a–b → `test_compiled_graph_shared_by_run_and_registry`, `test_list_registered_workflows_memoizes_compiled_graph` (existing)
- [x] **9.** RF10 response helper — T-RF10a → `test_t_rf10_workflow_state_to_run_response_maps_state_fields` (added)
- [x] **10.** RF10 consumers — T-RF10b–c → `test_t24_run_workflow_returns_graph_counts`, `test_post_run_workflow_returns_response_when_wired` (existing)
- [x] **11.** RF11 domain errors — T-RF11a–b → `test_t32_uninitialized_workflow_maps_to_not_found_error`, `test_post_run_workflow_returns_503_when_uninitialized` (existing)
- [x] **12.** RF12 retry policy — T-RF12 → `test_llm05e_graph_derive_and_merge_nodes_use_read_retry_policy` (existing)
- [x] **13.** RF21 INFO hit-rate — T-RF21 → `test_c38_cache_hit_rate_logged_at_info` (existing)
- [x] **14.** Run `uv sync --frozen`
- [x] **15.** Run `uv run ruff check src/ tests/`
- [x] **16.** Run `uv run pytest -v`
- [x] **17.** Write `HOMOLOGATION.md` coverage matrix for TEST13
- [x] **18.** Set TEST13.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_entrypoint.py` | T-RF01a | existing |
| `tests/interface/test_local_ui_api.py` | T-RF01b, T-RF10c, T-RF11b | existing |
| `tests/test_workflows.py` | T-RF03a–c | existing |
| `tests/test_cache.py` | T-RF02, T-RF07, T-RF04b, T-RF21 | existing |
| `tests/test_llm.py` | T-RF08, T-RF04a, T-RF12 | existing |
| `tests/test_agent.py` | T-RF09a–b | existing |
| `tests/test_validation.py` | T-RF10a | **added** |
| `tests/test_interface_tools.py` | T-RF10b, T-RF11a | existing |

### Verification results

```text
uv run ruff check src/ tests/  → All checks passed!
uv run pytest -v               → 156 passed
```
