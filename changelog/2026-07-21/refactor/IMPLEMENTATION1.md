# Implementation 1: REFACTOR2 actionable items (non-BL-022)

**Date:** 2026-07-21
**Layer:** refactor (cross-cutting)
**Investigation:** [INVESTIGATION1.md](./INVESTIGATION1.md)
**Status:** done

## Summary

Implement 11 REFACTOR2 items reusing `run_cache_aside`, lazy workflow DI, shared graph memoization, domain error mapping, and INFO cache metrics. Update tests per acceptance criteria.

## Checklist

- [x] **1.** RF01 — Bootstrap `local_ui_main.py` with composition root
- [x] **2.** RF03 — Cancel provisional YouTube task in `retrieve_with_videos`
- [x] **3.** RF02 — MCP tool cache singleflight via `run_cache_aside`
- [x] **4.** RF07 — Payload size guard (included in `run_cache_aside` path)
- [x] **5.** RF08 — LLM cache singleflight via `run_cache_aside`
- [x] **6.** RF04 — Lazy-init `DocumentVideoWorkflow` at composition root
- [x] **7.** RF09 — Memoize compiled graph (`_get_compiled_graph`)
- [x] **8.** RF10 — Extract `workflow_state_to_run_response` helper
- [x] **9.** RF11 — Map uninitialized workflow to `ResourceNotFoundError`
- [x] **10.** RF12 — Read retry policy on derive/merge nodes
- [x] **11.** RF21 — Export cache hit-rate at INFO
- [x] **12.** Tests — RF01 local UI bootstrap, RF03 cancel, RF02 singleflight, RF09 memoization
- [x] **13.** Run `uv run ruff check src/ tests/` and fix issues
- [x] **14.** Run `uv run mypy src/`
- [x] **15.** Run `uv run pytest`
- [x] **16.** Update investigation/implementation status

## Task details

### 1. RF01 — local_ui_main bootstrap

- **File(s):** `local_ui_main.py`
- **Done when:** `main()` calls `bootstrap_environment`, `load_settings`, `configure_logging`, `load_operational_config`, `initialize_application_runtime` before uvicorn

### 2. RF03 — YouTube cancel on refinement

- **File(s):** `application/workflows.py`, `tests/test_workflows.py`
- **Done when:** Title differs from query → 1 YouTube call; parallel path preserved when terms match

### 3–5. RF02/RF07/RF08 — Cache hardening

- **File(s):** `mcp_tool_cache.py`, `cached_llm.py`, `tests/test_cache.py`, `tests/test_llm.py`
- **Done when:** Parallel miss invokes once; oversize MCP payload skips `set`

### 6. RF04 — Lazy workflow

- **File(s):** `workflow_runtime.py`, `wiring.py`, `tests/test_cache.py`, `tests/test_llm.py`
- **Done when:** Boot does not build workflow; first `get_document_video_workflow()` builds

### 7. RF09 — Graph memoization

- **File(s):** `application/agent.py`, `tests/test_agent.py`
- **Done when:** Single compile across run + registry; `reset_compiled_graph_cache()` for tests

### 8–9. RF10/RF11 — Interface consolidation

- **File(s):** `validation.py`, `custom_tools.py`, `local_ui/api.py`, `agent.py`, tests
- **Done when:** Shared helper used; uninitialized workflow → `ResourceNotFoundError` / mapped HTTP

### 10. RF12 — Retry policy

- **File(s):** `application/agent.py`, `tests/test_llm.py`
- **Done when:** derive/merge nodes use `_read_node_retry_policy()`

### 11. RF21 — Cache metrics INFO

- **File(s):** `cache_observability.py`, `tests/test_cache.py`
- **Done when:** INFO log shows hit-rate after N operations

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed
- [x] Changes match ARCHITECTURE.md layer rules

## Remediation (CODE_REVIEW1)

**Date:** 2026-07-21  
**Trigger:** Stage 3 remediation after CODE_REVIEW1 (approve with nits)

| Warning | Fix | Verification |
| :--- | :--- | :--- |
| `ruff format --check` fails on `tests/test_cache.py` | Ran `uv run ruff format tests/test_cache.py` | `uv run ruff format --check src/ tests/` passes |
| RF01 bootstrap lost under uvicorn `reload=True` worker | Extracted `bootstrap_application_runtime()` in `main.py`; added FastAPI lifespan hook in `interface/local_ui/api.py` (`bootstrap_runtime=True` on module `app`); `local_ui_main.py` reuses shared bootstrap (idempotent double-init in parent + worker) | `test_local_ui_lifespan_bootstraps_application_runtime`; `test_e06` updated |
