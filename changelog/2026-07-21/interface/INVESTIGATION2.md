# Investigation 2: Memoize UI workflow list and config.json defaults

**Date:** 2026-07-21
**Layer:** interface
**Status:** approved

## User request

Execute backlog tasks BL-023 and BL-027 together:

- **BL-023:** Cache `list_registered_workflows()` at module level; avoid `build_document_video_graph()` on every `/api/workflows` request; add test or manual check for UI list endpoint.
- **BL-027:** Load `DEFAULT_WORKFLOW_EXECUTION_CONFIG` from `config.json`; remove hardcoded duplicate defaults in `workflow_config.py`; add test that Python fallback matches committed `config.json`.

## Architecture alignment

- **Layers touched:** interface (primary — local UI perf), application (`agent.py`, `workflow_config.py`), entrypoint-adjacent (`operational_config.py` loader reused for defaults)
- **Patterns applied:** Module-level memoization for dev-only UI metadata; single source of truth for operational defaults via existing `load_operational_config()` + `config.json`
- **Anti-patterns avoided:** No graph rebuild in FastAPI route handlers; no third copy of default integers in Python

## Current state

| Asset | Status |
| :--- | :--- |
| `application/agent.py` | `list_registered_workflows()` calls `build_document_video_graph()` on every invocation |
| `interface/local_ui/api.py` | `_workflow_index()` calls `list_registered_workflows()` per GET list/detail |
| `application/workflow_config.py` | `DEFAULT_WORKFLOW_EXECUTION_CONFIG` hardcodes `3/300/60` duplicating `config.json` |
| `operational_config.py` | Canonical `load_operational_config()` from repo-root `config.json` |
| `tests/interface/test_local_ui_api.py` | `test_list_workflows_returns_langgraph_metadata` covers UI list endpoint |
| `tests/test_llm.py` | `test_llm12_default_workflow_execution_config_matches_config_json` already asserts DEFAULT vs `config.json` |

Performance audit P10 and code-health D04 both flag these issues.

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Graph recompiled per UI request | application → interface | P1 |
| Duplicate config defaults | application | P1 |
| No assertion that memoization works | tests | P2 |

## Minimal increment

Memoize the registered-workflow list (including its compiled graph) in `agent.py` with a test-only reset helper. Derive `DEFAULT_WORKFLOW_EXECUTION_CONFIG` at module import by loading `config.json` through `operational_config.load_operational_config()` and mapping fields to `WorkflowExecutionConfig`. Existing LLM12 and UI list tests satisfy acceptance; add one unit test proving `build_document_video_graph` is not called on repeated `list_registered_workflows()` invocations.

### Scope (in)

- `application/agent.py` — module cache + `reset_registered_workflows_cache()`
- `application/workflow_config.py` — load DEFAULT from `config.json`
- `tests/test_agent.py` (or extend interface tests) — memoization behavior test

### Scope (out / deferred)

- Caching `create_agent()` / `run_document_video_graph()` (execution path still builds per run)
- Backlog markdown update (master after homologation)
- Changing `OperationalConfig` Pydantic field defaults (file remains source of truth)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `application/agent.py` | modify | Module-level memo for `list_registered_workflows()` |
| `application/workflow_config.py` | modify | Derive DEFAULT from `config.json` via loader |
| `tests/test_agent.py` | create | Assert graph build happens once across repeated list calls |

## Dependencies & environment

- No new packages
- Relies on committed `config.json` at repo root
- Commands: `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Import-time file read:** `workflow_config` import now reads `config.json`; missing file fails at import (acceptable — same as startup requirement).
- **Test isolation:** Memoization cache must be reset in tests that monkeypatch graph builder.

## Handoff to implementation

IMPLEMENTATION2.md: workflow_config defaults first, then agent memoization, then memoization test, then lint/type/test gates.
