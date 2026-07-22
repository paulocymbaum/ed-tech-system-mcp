# Code Review 1: REFACTOR2 actionable items (non-BL-022)

**Date:** 2026-07-21
**Layer:** refactor (cross-cutting)
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)
- [REFACTOR2.md](./REFACTOR2.md)
- [PERFORMANCE_AUDIT2.md](../performance/PERFORMANCE_AUDIT2.md)
- [CODE_HEALTH_AUDIT2.md](../code-health/CODE_HEALTH_AUDIT2.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `f098585` | Enhance refactor planning and audit orchestration |
| `2717a17` | Enhance error handling and logging configuration |
| `4bd5985` | Enhance MCP tool integration and caching mechanisms |
| `9d3b786` | Refactor LLM model loading and improve configuration handling |
| `c5b5a60` | Enhance LLM integration and operational configuration |
| `eef9003` | Refactor caching logic and enhance workflow integration |
| `80bb4ce` | Add workflow-ui script and integrate FastAPI and Uvicorn dependencies |
| `4b2835d` | include redis cache logic |

## Summary

All 11 in-scope REFACTOR2 items (RF01, RF03, RF02, RF04, RF07, RF08, RF09, RF10, RF11, RF12, RF21) are implemented with matching acceptance tests. Layer boundaries remain clean: `run_cache_aside` centralizes singleflight and payload guards in infrastructure; lazy workflow DI mirrors the existing LLM pattern; interface consolidation and domain error mapping are consistent across MCP and local UI paths. Verification gates pass except `ruff format --check` on one test file. No secrets in diff; BL-022 adapter stubs correctly remain out of scope.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | All 11 RF items in scope delivered; RF05/RF06 and RF13–RF20 correctly excluded |
| IMPLEMENTATION1 | Checklist 1–16 checked; matches code and tests |
| REFACTOR2 | Execution order followed; deferred items untouched |
| ARCHITECTURE.md | No layer violations; composition-root bootstrap parity achieved for local UI |
| ENVIRONMENT_SETUP.md | `ruff check`, `mypy`, `pytest` pass; format check not in IMPLEMENTATION1 gate but fails on `tests/test_cache.py` |
| PERFORMANCE_AUDIT2 | P02, P03, P04, P07, P08, P09, P12, P16 findings addressed by this increment |
| CODE_HEALTH_AUDIT2 | H02, D01, D02, A01 findings addressed; H04 (BL-022 stubs) still deferred |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| RF01 — bootstrap `local_ui_main.py` | `local_ui_main.py` calls `bootstrap_environment` → `initialize_application_runtime` before `uvicorn.run` | match |
| RF03 — cancel provisional YouTube task | `workflows.py:78-81` cancels `videos_task` on title refinement; `test_t19c` expects 1 call | match |
| RF02 — MCP cache singleflight | `mcp_tool_cache.py` routes miss path through `run_cache_aside`; `test_c36` | match |
| RF07 — MCP payload size guard | Guard in `run_cache_aside:77-78`; `test_c37` | match |
| RF08 — LLM cache singleflight | `cached_llm.py:133-142` uses `run_cache_aside`; `test_llm04c` | match |
| RF04 — lazy `DocumentVideoWorkflow` | `workflow_runtime.py` lazy builder; `wiring.py:226`; `test_llm06b`, `test_c21` | match |
| RF09 — memoize compiled graph | `agent.py:_get_compiled_graph`; `test_compiled_graph_shared_by_run_and_registry` | match |
| RF10 — `workflow_state_to_run_response` | `validation.py:85-96`; used in `custom_tools.py` and `local_ui/api.py` | match |
| RF11 — `ResourceNotFoundError` mapping | `agent.py:68`, `custom_tools.py:41,54`, `local_ui/api.py:86-87`; `test_t32`, `test_post_run_workflow_returns_503_when_uninitialized` | match |
| RF12 — read retry on derive/merge | `build_document_video_graph` uses `_read_node_retry_policy()` on derive/merge; `test_llm05e` | match |
| RF21 — INFO cache hit-rate | `cache_observability.py:_maybe_log_hit_rate`; `test_c38` | match |
| BL-022 adapters (RF05/RF06) | Stubs unchanged | match (deferred) |
| RF13–RF20 deferrals | Not implemented | match (deferred) |

## Layer review (refactor / cross-cutting)

### Files reviewed

- `src/mcp_server/local_ui_main.py` — RF01 composition-root bootstrap parity with `main.py`
- `src/mcp_server/application/workflows.py` — RF03 provisional YouTube task cancellation
- `src/mcp_server/application/workflow_runtime.py` — RF04 lazy workflow accessor
- `src/mcp_server/application/agent.py` — RF09 graph memo, RF11 domain error, RF12 retry policy
- `src/mcp_server/wiring.py` — RF04 lazy-init registration; `document_video_workflow=None` at boot
- `src/mcp_server/infrastructure/mcp_tool_cache.py` — RF02 singleflight via `run_cache_aside`
- `src/mcp_server/infrastructure/cached_llm.py` — RF08 singleflight via `run_cache_aside`
- `src/mcp_server/infrastructure/cache_aside.py` — RF02/RF07/RF08 shared coordinator + payload guard
- `src/mcp_server/infrastructure/cache_observability.py` — RF21 INFO hit-rate logging
- `src/mcp_server/interface/validation.py` — RF10 response mapper
- `src/mcp_server/interface/custom_tools.py` — RF10/RF11 MCP path
- `src/mcp_server/interface/local_ui/api.py` — RF10/RF11 HTTP 503 mapping
- `tests/test_entrypoint.py`, `tests/test_workflows.py`, `tests/test_cache.py`, `tests/test_llm.py`, `tests/test_agent.py`, `tests/interface/test_local_ui_api.py`, `tests/test_interface_tools.py` — acceptance coverage

### Architecture & patterns

- **Composition root:** `initialize_application_runtime` defers workflow and LLM construction; MCP tool cache remains eager (lightweight). `ApplicationContext.document_video_workflow` is `None` until first `get_document_video_workflow()` — aligns with investigation risk note on `test_c21`.
- **Cache hardening:** MCP tool and LLM caches now share `run_cache_aside` with port adapters — eliminates D02 duplication and closes P03/P07 stampede gaps.
- **Interface boundary:** `workflow_state_to_run_response` is the single response-shape mapper; `ResourceNotFoundError` flows through `raise_as_mcp_error` (MCP) and `HTTPException(503)` (local UI).
- **Graph efficiency:** `_get_compiled_graph()` serves both `run_document_video_graph` and `list_registered_workflows`; `reset_compiled_graph_cache()` paired with `reset_registered_workflows_cache()` for test isolation.
- **Entrypoint:** `load_dotenv()` remains only in `main.bootstrap_environment()`; `local_ui_main` reuses that helper — no new dotenv call sites.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (workflow delegates to ports; no direct YouTube in tools)
- [x] No secrets in source or changelog
- [x] BL-022 adapter stubs not silently “fixed” in this increment

## RF item verification

| RF | Verification evidence | Result |
| :--- | :--- | :--- |
| RF01 | `local_ui_main.py:19-23`; `test_e06_local_ui_main_bootstraps_application_runtime` | pass |
| RF03 | `workflows.py:65-82`; `test_t19c` (`call_count == 1`); `test_t19d` parallel path preserved | pass |
| RF02 | `mcp_tool_cache.py:39-48`; `test_c36_mcp_tool_cache_parallel_misses_invoke_once` | pass |
| RF04 | `workflow_runtime.py:36-61`, `wiring.py:226-233`; `test_llm06b`, `test_c21` (`document_video_workflow is None`) | pass |
| RF07 | `cache_aside.py:77-78`; `test_c37_mcp_tool_cache_skips_oversize_payload` | pass |
| RF08 | `cached_llm.py:133-142`; `test_llm04c_cached_chat_model_parallel_misses_invoke_inner_once` | pass |
| RF09 | `agent.py:152-165,221,242`; `test_compiled_graph_shared_by_run_and_registry` (`build_count == 1`) | pass |
| RF10 | `validation.py:workflow_state_to_run_response`; both MCP and local UI call sites | pass |
| RF11 | `ResourceNotFoundError` in agent/tools; `test_t32`, `test_post_run_workflow_returns_503_when_uninitialized` | pass |
| RF12 | `test_llm05e_graph_derive_and_merge_nodes_use_read_retry_policy` | pass |
| RF21 | `cache_observability.py:60-71`; `test_c38_cache_hit_rate_logged_at_info` | pass |

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **`ruff format --check` fails on `tests/test_cache.py`.** `uv run ruff format --check src/ tests/` reports one file would be reformatted. Lint (`ruff check`) and tests pass, but CI or contributors running the full format gate will fail until the file is formatted.
- **RF01 bootstrap may not survive uvicorn `reload=True` in the worker subprocess.** `local_ui_main.py` calls `initialize_application_runtime` in the parent process before `uvicorn.run(..., reload=True)`. The reload worker imports `mcp_server.interface.local_ui.api:app` directly and does not re-execute `main()`. Manual `uv run workflow-ui` with default `reload=True` can leave the serving worker without a wired workflow, causing POST `/api/workflows/{id}/run` to return 503 despite RF01. Unit test `test_e06` mocks `uvicorn.run` and does not catch this integration gap. Consider a FastAPI lifespan hook or `reload=False` for the composition-root path (REFACTOR2 P15 remains deferred).

### Suggestions (consider)

- **`create_agent()` still compiles a fresh graph** (`agent.py:168-170`) and bypasses `_get_compiled_graph()`. No production callers today; REFACTOR2 explicitly keeps this facade (R01). If future code calls `create_agent()` alongside `run_document_video_graph`, memoization benefit is lost.
- **`workflows.py` module docstring** (lines 56–60) still describes the title-refinement path as a “second sequential YouTube call replaces the provisional results” without mentioning cancellation of the provisional task. Behavior is correct; doc could note the cancel-and-refetch pattern for maintainers.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/ tests/` | pass |
| `uv run ruff format --check src/ tests/` | **fail** — `tests/test_cache.py` would be reformatted |
| `uv run mypy src/` | pass (44 source files) |
| `uv run pytest` | pass (154 passed, 1 deprecation warning) |

## Verdict

**approve with nits**

All 11 in-scope REFACTOR2 items are implemented with evidence-based tests, architecture boundaries are respected, and core CI gates (`ruff check`, `mypy`, `pytest`) pass. Approve with nits: run `ruff format` on `tests/test_cache.py` before merge, and track the uvicorn reload + composition-root interaction as a follow-up if local UI dev workflow remains flaky after RF01.
