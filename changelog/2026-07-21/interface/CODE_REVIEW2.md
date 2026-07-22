# Code Review 2: Memoize UI workflow list and config.json defaults

**Date:** 2026-07-21
**Layer:** interface
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION2.md](./INVESTIGATION2.md)
- [IMPLEMENTATION2.md](./IMPLEMENTATION2.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `c5b5a60` | Enhance LLM integration and operational configuration *(introduces `workflow_config.py` with hardcoded defaults)* |
| `eef9003` | Refactor caching logic and enhance workflow integration *(LangGraph agent wiring)* |
| `4bd5985` | Enhance MCP tool integration and caching mechanisms *(`list_registered_workflows()` without memoization)* |
| `80bb4ce` | Add workflow-ui script and integrate FastAPI and Uvicorn dependencies *(local UI calls `list_registered_workflows`)* |

**Working tree (uncommitted, IMPLEMENTATION2 delta):** `agent.py` module cache + `reset_registered_workflows_cache()`; `workflow_config.py` loads `DEFAULT_WORKFLOW_EXECUTION_CONFIG` via `load_operational_config()`; new `tests/test_agent.py`; changelog `INVESTIGATION2.md` / `IMPLEMENTATION2.md`.

## Summary

INVESTIGATION2 and IMPLEMENTATION2 are **delivered in the working tree**: `list_registered_workflows()` memoizes the compiled graph at module level (BL-023), eliminating per-request LangGraph recompilation on local UI `/api/workflows` paths; `DEFAULT_WORKFLOW_EXECUTION_CONFIG` is derived from committed `config.json` via `load_operational_config()`, removing hardcoded `3/300/60` duplicates (BL-027). Interface code is unchanged — `local_ui/api.py` benefits indirectly. Architecture boundaries are respected; existing LLM12 and UI list tests plus new `test_agent.py` cover acceptance. Verdict is **request changes** because IMPLEMENTATION2 code and changelog files are **not committed**; HEAD still has uncached `list_registered_workflows()` and hardcoded defaults.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION2 | Scope (in) delivered in working tree. Application-primary changes filed under interface layer folder — aligned with investigation's layer table. Scope (out) items correctly deferred (execution-path graph builds, backlog markdown). |
| IMPLEMENTATION2 | All checklist items checked; verification results match independent re-run (140 pytest, ruff, mypy). Status `done` matches working-tree code. |
| ARCHITECTURE.md | Application orchestration unchanged; no infrastructure/MCP imports added. `operational_config` reuse is entrypoint-adjacent per investigation — acceptable for this increment. |
| ENVIRONMENT_SETUP.md | `config.json` remains canonical operational source; import-time read in `workflow_config` matches documented startup requirement for file presence. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `agent.py` — module cache + `reset_registered_workflows_cache()` | `_REGISTERED_WORKFLOWS`, `_build_registered_workflows()`, reset helper | match (uncommitted) |
| `workflow_config.py` — DEFAULT from `load_operational_config()` | `_default_workflow_execution_config()` at import; no literal `3/300/60` | match (uncommitted) |
| `tests/test_agent.py` — memoization unit test | `test_list_registered_workflows_memoizes_compiled_graph` with monkeypatch counter | match (uncommitted) |
| Rely on LLM12 for config parity | `test_llm12_default_workflow_execution_config_matches_config_json` passes | match |
| Rely on UI list test for endpoint | `test_list_workflows_returns_langgraph_metadata` passes | match |
| Deferred: cache `create_agent()` / `run_document_video_graph()` | Still builds per invocation | match (deferred) |
| Deferred: BACKLOG BL-023/BL-027 status update | `BACKLOG.md` still `open` | match (deferred) |

## Layer review (interface)

### Files reviewed

- `src/mcp_server/application/agent.py` — module-level `_REGISTERED_WORKFLOWS` cache; `_build_registered_workflows()` extracts build logic; `reset_registered_workflows_cache()` for test isolation
- `src/mcp_server/application/workflow_config.py` — `DEFAULT_WORKFLOW_EXECUTION_CONFIG` loaded from `config.json` via `load_operational_config()`; runtime get/set unchanged
- `src/mcp_server/operational_config.py` — canonical loader reused (no changes in this increment)
- `src/mcp_server/interface/local_ui/api.py` — consumer: `_workflow_index()` → `list_registered_workflows()`; benefits from memoization without modification
- `tests/test_agent.py` — asserts single `build_document_video_graph` call and identity (`first is second`) across two list calls
- `tests/test_llm.py` — LLM12 config parity (pre-existing)
- `tests/interface/test_local_ui_api.py` — UI01 list endpoint metadata (pre-existing)

### Architecture & patterns

- Primary code changes sit in **application** layer; interface layer is the performance beneficiary — consistent with INVESTIGATION2's "interface (primary — local UI perf)" framing.
- Memoization is module-scoped and dev-UI-oriented; execution path (`run_document_video_graph` → `create_agent` → `build_document_video_graph`) intentionally remains uncached per scope (out).
- `_workflow_runtime_config()` fallback to `DEFAULT_WORKFLOW_EXECUTION_CONFIG` now reads the same `config.json` values as `main.py` startup wiring, closing D04 drift risk.
- `reset_registered_workflows_cache()` is exported for tests; no production invalidation path needed (process restart suffices for graph definition changes).

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (no new infrastructure imports in application/interface)
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **IMPLEMENTATION2 deliverables are uncommitted.** At HEAD (`4bd5985`), `list_registered_workflows()` still calls `build_document_video_graph()` on every invocation and `workflow_config.py` hardcodes `node_retries=3`, `workflow_timeout_seconds=300`, `agent_node_timeout_seconds=60`. The memoization cache, config.json-derived defaults, `tests/test_agent.py`, and `INVESTIGATION2.md` / `IMPLEMENTATION2.md` exist only in the working tree. Merging `testbranch` as-is would not ship BL-023 or BL-027.

### Warnings (should fix)

- **BACKLOG BL-023 and BL-027 remain `open`.** Investigation defers backlog update to master after homologation; until then, traceability between delivered code and backlog status is stale.
- **`_workflow_index()` still rebuilds the `WorkflowGraphView` dict on every GET.** Graph compilation is memoized (the P10 bottleneck), but `workflow_graph_view()` projection runs per request for list and detail routes. Acceptable for this increment; a follow-up could cache the view index if profiling warrants it.
- **Application imports entrypoint-adjacent `operational_config`.** `workflow_config.py` now depends on `load_operational_config()` at import time. Planned and safe for `config.json`, but couples application defaults to the file loader rather than injected startup config.

### Suggestions (consider)

- Add an autouse pytest fixture that calls `reset_registered_workflows_cache()` if future tests monkeypatch `build_document_video_graph` without explicit reset.
- Document in `ENVIRONMENT_SETUP.md` or `workflow_config.py` docstring that `DEFAULT_WORKFLOW_EXECUTION_CONFIG` is fixed at import — editing `config.json` requires process restart (same as `main.py` operational load).

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass |
| `uv run pytest` | pass (140 tests) |

## Verdict

**request changes**

Working-tree code matches INVESTIGATION2 / IMPLEMENTATION2 intent, closes P10 graph recompilation and D04 config duplication, respects layer boundaries, and passes all quality gates. **Commit** `agent.py`, `workflow_config.py`, `tests/test_agent.py`, and changelog artifacts before merge; update BACKLOG BL-023/BL-027 after homologation per deferred scope.
