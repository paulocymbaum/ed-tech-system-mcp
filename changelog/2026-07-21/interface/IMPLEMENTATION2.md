# Implementation 2: Memoize UI workflow list and config.json defaults

**Date:** 2026-07-21
**Layer:** interface
**Investigation:** [INVESTIGATION2.md](./INVESTIGATION2.md)
**Status:** done

## Summary

Derive `DEFAULT_WORKFLOW_EXECUTION_CONFIG` from committed `config.json` at import time, eliminating hardcoded duplicates. Cache the result of `list_registered_workflows()` (including its compiled graph) at module level so local UI `/api/workflows` endpoints do not recompile LangGraph on every request. Add a unit test for memoization; rely on existing UI list and LLM12 tests for endpoint and config parity.

## Checklist

- [x] **1.** Load `DEFAULT_WORKFLOW_EXECUTION_CONFIG` from `config.json` in `workflow_config.py`
- [x] **2.** Memoize `list_registered_workflows()` in `agent.py` with `reset_registered_workflows_cache()` for tests
- [x] **3.** Add `tests/test_agent.py` — memoization calls `build_document_video_graph` once
- [x] **4.** Run `uv run ruff check src/` and fix issues
- [x] **5.** Run `uv run mypy src/`
- [x] **6.** Run `uv run pytest`
- [x] **7.** Update investigation/implementation status to done

## Task details

### 1. Config defaults from config.json

- **File(s):** `src/mcp_server/application/workflow_config.py`
- **Done when:** `DEFAULT_WORKFLOW_EXECUTION_CONFIG` is built via `load_operational_config()` mapping; no literal `3/300/60` in file

### 2. Memoize registered workflows

- **File(s):** `src/mcp_server/application/agent.py`
- **Done when:** Second call to `list_registered_workflows()` returns same list object without calling `build_document_video_graph()` again

### 3. Memoization test

- **File(s):** `tests/test_agent.py`
- **Done when:** Monkeypatched counter shows single graph build across two list calls; cache reset in fixture

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Verification results

```
uv run ruff check src/  → All checks passed!
uv run mypy src/        → Success: no issues found in 44 source files
uv run pytest           → 140 passed
```

## Remediation (CODE_REVIEW2)

**Verdict:** request changes — critical finding was uncommitted increment only (skipped per remediation scope; no git/commit action).

**Code changes:** none required. Re-read of [CODE_REVIEW2.md](./CODE_REVIEW2.md) confirms working-tree implementation matches INVESTIGATION2 intent; no defects identified.

**Gates re-verified (remediation pass):**

```
uv run ruff check src/  → All checks passed!
uv run mypy src/        → Success: no issues found in 44 source files
uv run pytest           → 140 passed
```

**Deferred (accepted per review):**

- BACKLOG BL-023 / BL-027 status update — master after homologation
- `_workflow_index()` still rebuilds `WorkflowGraphView` dict per request — graph compilation memoized; view projection cache deferred
- `workflow_config.py` imports `load_operational_config()` at import time — intentional per INVESTIGATION2 / D04 design
