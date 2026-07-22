# Investigation 1: REFACTOR2 actionable items (non-BL-022)

**Date:** 2026-07-21
**Layer:** refactor (cross-cutting: entrypoint, application, infrastructure, interface)
**Status:** approved

## User request

Implement all IN-scope RF items from [REFACTOR2.md](./REFACTOR2.md) (final): RF01, RF03, RF02, RF04, RF07, RF08, RF09, RF10, RF11, RF12, RF21. Exclude BL-022 (RF05/RF06), deferred RF13–RF20.

## Architecture alignment

- **Layers touched:** entrypoint (`local_ui_main.py`), application (`workflows.py`, `agent.py`, `workflow_runtime.py`), infrastructure (`mcp_tool_cache.py`, `cached_llm.py`, `cache_observability.py`), interface (`validation.py`, `custom_tools.py`, `local_ui/api.py`), composition root (`wiring.py`)
- **Patterns applied:** composition-root bootstrap parity, lazy DI (mirror `configure_lazy_chat_model`), cache-aside singleflight via `run_cache_aside()`, domain error mapping at interface boundary, graph memoization
- **Anti-patterns avoided:** no adapter HTTP bodies (BL-022), no `load_dotenv()` outside entrypoints, no infrastructure imports in domain

## Current state

| RF | File(s) | Current behavior | Gap |
| :--- | :--- | :--- | :--- |
| RF01 | `local_ui_main.py` | Uvicorn only; no `initialize_application_runtime` | POST `/api/workflows/{id}/run` hits uninitialized workflow |
| RF03 | `workflows.py:64-76` | `asyncio.gather` always completes both tasks; title refinement causes 2 YouTube calls | `test_t19c` expects `call_count == 2` |
| RF02 | `mcp_tool_cache.py:43-45` | Miss path invokes directly; no singleflight | Duplicate cold-key tool work under concurrency |
| RF04 | `wiring.py:222-224` | Eager `build_document_video_workflow` at boot | Adapters built even for `health_check`-only boot |
| RF07 | `mcp_tool_cache.py:45` | Unconditional `cache.set` | Oversize MCP payloads can bloat Redis |
| RF08 | `cached_llm.py:128-135` | Miss path invokes inner directly | Concurrent identical prompts duplicate Groq calls |
| RF09 | `agent.py:206,227` | `create_agent()` / `build_document_video_graph()` per `run_document_video_graph`; separate memo in `list_registered_workflows` | Two compiles for same graph definition |
| RF10 | `custom_tools.py`, `local_ui/api.py` | Duplicated `WorkflowRunResponse` construction | DRY violation at interface boundary |
| RF11 | `agent.py:67`, `custom_tools.py:40,54` | `RuntimeError` on missing workflow | Unmapped generic 500 on MCP hot paths |
| RF12 | `agent.py:116,140` | `derive_search_terms` / `merge_results` use `_node_retry_policy()` (4 attempts) | CPU-only nodes inherit full I/O retry budget |
| RF21 | `cache_observability.py` | DEBUG-only hit/miss logs; global counters only | No INFO hit-rate for production tuning |

**Existing helpers to reuse:**
- `run_cache_aside()` in `cache_aside.py` — singleflight + `payload_within_cache_limit`
- `configure_lazy_chat_model` / `get_chat_model` in `llm.py` — pattern for RF04
- `ResourceNotFoundError` + `raise_as_mcp_error` — pattern for RF11
- `test_c32` parallel miss test — mirror for MCP tool and LLM cache

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Local UI missing composition root | entrypoint | High |
| Duplicate YouTube on title refinement | application | High |
| MCP/LLM cache stampede | infrastructure | High |
| Eager workflow wiring | entrypoint/wiring | High |
| Graph double-compile | application | Medium |
| Duplicated response mapper | interface | Medium |
| RuntimeError vs DomainError | interface/application | Medium |
| Over-retry on CPU nodes | application | Medium |
| Cache metrics at INFO | infrastructure | Low |

## Minimal increment

Single cross-cutting refactor increment implementing all 11 RF items in REFACTOR2 recommended order. Reuses `run_cache_aside` for RF02/RF07/RF08; mirrors lazy LLM pattern for RF04; shares one memoized compiled graph for RF09 run + registry paths.

### Scope (in)

- RF01, RF03, RF02, RF04, RF07, RF08, RF09, RF10, RF11, RF12, RF21
- Tests: local UI bootstrap (RF01), title-refinement cancel (RF03), MCP singleflight (RF02), graph memoization (RF09), plus coverage for RF04/RF07/RF08/RF10/RF11/RF12/RF21

### Scope (out / deferred)

- RF05, RF06, RF17 (BL-022 adapters)
- RF13–RF16, RF18–RF20 (product/ops deferrals per REFACTOR2)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `local_ui_main.py` | modify | RF01 bootstrap parity |
| `application/workflows.py` | modify | RF03 cancel provisional video task |
| `infrastructure/mcp_tool_cache.py` | modify | RF02 singleflight, RF07 payload guard via `run_cache_aside` |
| `infrastructure/cached_llm.py` | modify | RF08 singleflight via `run_cache_aside` |
| `application/workflow_runtime.py` | modify | RF04 lazy workflow accessor |
| `wiring.py` | modify | RF04 lazy-init registration |
| `application/agent.py` | modify | RF09 graph memo, RF11 domain error, RF12 retry policy |
| `interface/validation.py` | modify | RF10 `workflow_state_to_run_response` |
| `interface/custom_tools.py` | modify | RF10 helper use, RF11 domain errors |
| `interface/local_ui/api.py` | modify | RF10 helper use, RF11 HTTP mapping |
| `infrastructure/cache_observability.py` | modify | RF21 INFO hit-rate |
| `tests/*` | modify/add | Acceptance test coverage |

## Dependencies & environment

- No new runtime deps
- Commands: `uv sync --frozen`, `uv run ruff check src/ tests/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- RF04 changes `ApplicationContext.document_video_workflow` to `None` until first access — update `test_c21`
- RF09 shared graph cache requires `reset_compiled_graph_cache()` in tests alongside `reset_registered_workflows_cache()`
- RF03 changes `test_t19c` expectation from 2 → 1 YouTube call

## Handoff to implementation

IMPLEMENTATION1.md checklist follows REFACTOR2 execution order: RF01 → RF03 → RF02/RF07/RF08 → RF04/RF09 → RF10/RF11/RF12 → RF21, then verification gates and test updates.
