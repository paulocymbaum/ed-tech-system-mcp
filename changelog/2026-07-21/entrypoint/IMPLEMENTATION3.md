# Implementation 3: Composition root cache wiring and observability

**Date:** 2026-07-21
**Layer:** entrypoint
**Investigation:** [INVESTIGATION3.md](./INVESTIGATION3.md)
**Status:** done

## Summary

Create a single shared `ICacheStore` in `ApplicationContext` at the composition root, wire workflow/MCP tool cache/LLM through `initialize_application_runtime()`, expose runtime accessors to the interface layer, add typed MCP tool cache envelope and hit/miss observability, document production cache requirements, and verify with tests.

## Checklist

- [x] **1.** BL-003: Add `ApplicationContext` and pass shared cache to all builders in `wiring.py`
- [x] **2.** BL-003: Add test asserting single `create_cache_store` call per boot when cache enabled
- [x] **3.** BL-002: Add application runtime accessors (`workflow_runtime`, `mcp_tool_cache_runtime`)
- [x] **4.** BL-002: Wire workflow and MCP tool cache in `initialize_application_runtime()`
- [x] **5.** BL-002: Wrap `health_check` with `get_or_invoke` in `custom_tools.py`
- [x] **6.** BL-002: Add integration test for tool cache hit on identical args
- [x] **7.** BL-002: Annotate deferred `build_search_client` in `wiring.py`
- [x] **8.** BL-012: Document production cache in `ENVIRONMENT_SETUP.md`
- [x] **9.** BL-012: Document local cache var names (`.env.example` is gitignored — see ENVIRONMENT_SETUP.md)
- [x] **10.** BL-012: Confirm graceful degradation test still passes
- [x] **11.** BL-008: Add `McpToolCacheEnvelope` and wire in `mcp_tool_cache.py`
- [x] **12.** BL-008: Add round-trip test for complex tool result types
- [x] **13.** BL-018: Add `cache_observability.py` with debug logging and counters
- [x] **14.** BL-018: Hook observability into `cached_adapters.py` and `cached_llm.py`
- [x] **15.** BL-018: Add test asserting hit log on second identical call
- [x] **16.** Update `BACKLOG.md` for BL-003, BL-002, BL-012, BL-008, BL-018
- [x] **17.** Run `uv run ruff check src/` and fix issues
- [x] **18.** Run `uv run mypy src/`
- [x] **19.** Run `uv run pytest`
- [x] **20.** Update investigation/implementation status to done

## Task details

### 1. ApplicationContext (BL-003)

- **File(s):** `wiring.py`
- **Done when:** `create_cache_store` called once in `initialize_application_runtime`; builders accept optional `cache` parameter

### 5. health_check cache wrapper (BL-002)

- **File(s):** `custom_tools.py`
- **Done when:** Async tool uses `get_mcp_tool_cache().get_or_invoke("health_check", {}, invoker)`

### 11. Typed envelope (BL-008)

- **File(s):** `cache_envelope.py`, `mcp_tool_cache.py`
- **Done when:** No `json.dumps(default=str)` or `# type: ignore` on deserialize path

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Remediation (CODE_REVIEW3)

**Status:** done — review findings addressed; **git commit pending user action** (per user constraint: no commits in this pass).

### Critical (deferred — user action required)

- [ ] **Commit increment 3** before merge. All files below belong to this increment and are uncommitted at remediation time.

**Files in increment 3:**

| Path | State |
| :--- | :--- |
| `src/mcp_server/wiring.py` | modified |
| `src/mcp_server/application/workflow_runtime.py` | new |
| `src/mcp_server/application/mcp_tool_cache_runtime.py` | new |
| `src/mcp_server/infrastructure/cache_envelope.py` | new |
| `src/mcp_server/infrastructure/cache_observability.py` | new |
| `src/mcp_server/infrastructure/cached_adapters.py` | modified |
| `src/mcp_server/infrastructure/cached_llm.py` | modified |
| `src/mcp_server/infrastructure/mcp_tool_cache.py` | modified |
| `src/mcp_server/interface/custom_tools.py` | modified |
| `tests/test_cache.py` | modified |
| `tests/test_interface_tools.py` | modified |
| `tests/test_operational_config.py` | modified |
| `tests/test_entrypoint.py` | modified (remediation) |
| `tests/test_llm.py` | modified (remediation) |
| `ENVIRONMENT_SETUP.md` | modified |
| `ARCHITECTURE.md` | modified (remediation) |
| `backlog/BACKLOG.md` | modified |
| `changelog/2026-07-21/entrypoint/INVESTIGATION3.md` | new |
| `changelog/2026-07-21/entrypoint/IMPLEMENTATION3.md` | new |
| `changelog/2026-07-21/entrypoint/CODE_REVIEW3.md` | new |

### Warnings fixed

- [x] **`.env.example` policy (BL-012):** `ENVIRONMENT_SETUP.md` no longer claims a committed `.env.example`; documents that `*.env.*` is gitignored and production checklist lives in `ENVIRONMENT_SETUP.md` + Doppler bootstrap. Item 9 clarified: local `.env.example` comments are optional and not version-controlled.
- [x] **Builder fallback bypass:** `build_chat_model`, `build_document_video_workflow`, and `build_mcp_tool_cache` raise `ValueError` when `CACHE_ENABLED=true` and `cache is None`; docstrings mark composition-root-only usage. Tests updated (`test_llm07`, `test_llm07b`).
- [x] **`ARCHITECTURE.md` file tree drift:** Added `ApplicationContext` note in `wiring.py`, `workflow_runtime.py`, `mcp_tool_cache_runtime.py`, `cache_envelope.py`, `cache_observability.py`.

### Warnings deferred

- [x] **`get_document_video_workflow()` has no MCP consumer yet** — deferred to BL-001; accessor is wired at startup for future orchestration tools.

### Optional suggestions implemented

- [x] `test_e01_main_startup_loads_operational_config_before_mcp_server` asserts `initialize_application_runtime` receives settings.
- [x] `test_c24_cached_llm_logs_hit_on_second_call` covers `cached_llm.py` observability hit path.

### Remediation verification

- [x] `uv run ruff check src/`
- [x] `uv run mypy src/`
- [x] `uv run pytest` (88 passed)
