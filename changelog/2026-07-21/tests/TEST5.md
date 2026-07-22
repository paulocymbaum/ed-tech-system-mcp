# Test Inventory 5: Composition root cache wiring and observability

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [entrypoint/INVESTIGATION3.md](../entrypoint/INVESTIGATION3.md), [entrypoint/IMPLEMENTATION3.md](../entrypoint/IMPLEMENTATION3.md), [entrypoint/CODE_REVIEW3.md](../entrypoint/CODE_REVIEW3.md)

## Scope

Validate increment 3 across entrypoint, application runtime accessors, interface, and infrastructure:

- Single shared `ICacheStore` in `ApplicationContext` at composition root (`wiring.py`) — BL-003
- Workflow and MCP tool cache wired via `initialize_application_runtime()`; `health_check` uses `get_or_invoke` — BL-002
- Production cache requirements in `ENVIRONMENT_SETUP.md`; Redis graceful degradation — BL-012
- Typed `McpToolCacheEnvelope` round-trip for complex tool results — BL-008
- Cache hit/miss debug logging and counters in cached adapters and LLM — BL-018

Existing coverage: `tests/test_cache.py` (C01–C24), `tests/test_interface_tools.py` (T20–T21), `tests/test_entrypoint.py` (E01), `tests/test_llm.py` (LLM07, LLM07b). Prior inventories TEST1–TEST4 remain valid for foundational cache and LLM contracts.

## Test catalog

### Entrypoint — composition root (BL-003)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C21 | `test_c21_initialize_application_runtime_creates_single_cache_store` | `initialize_application_runtime` single-store rule | `CACHE_ENABLED=true`, monkeypatch counting `create_cache_store` | Exactly one `create_cache_store` call; returns `ApplicationContext` with workflow and tool cache | Assert `create_calls == 1`; `isinstance(context, ApplicationContext)` |
| LLM07b | `test_llm07b_build_chat_model_requires_cache_store_when_enabled` | `build_chat_model` guard when cache enabled | `CACHE_ENABLED=true`, `cache=None` | `ValueError` with composition-root message | `pytest.raises(ValueError, match="cache store is required")` |
| E01 | `test_e01_main_startup_loads_operational_config_before_mcp_server` | `main()` bootstrap order and settings path | Patch startup chain | `initialize_application_runtime` receives `(operational_config, settings)` before MCP server | Assert call order and `runtime_args[0][1] is mock_settings` |

### Entrypoint — runtime wiring (BL-002)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C21 | `test_c21_initialize_application_runtime_creates_single_cache_store` | `ApplicationContext` fields | Cache-enabled boot | `document_video_workflow` and `mcp_tool_cache` non-None on context | Assert `context.document_video_workflow is not None` and `context.mcp_tool_cache is not None` |
| T21 | `test_t21_health_check_uses_tool_cache_on_second_identical_call` | `health_check` + `McpToolCachePort.get_or_invoke` | In-memory cache via `set_mcp_tool_cache` | Second identical call hits cache: one `set`, two `get` | Assert `cache.set_calls == 1`, `cache.get_calls == 2`, same return value |
| T20 | `test_t20_health_check_returns_ok` | `health_check` without cache runtime | `reset_mcp_tool_cache()` (autouse fixture) | Returns `"ok"` when no tool cache wired | Assert `await health_check() == "ok"` |

### Infrastructure — typed envelope (BL-008)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C22 | `test_c22_mcp_tool_cache_envelope_round_trips_complex_result` | `McpToolCacheEnvelope.pack` / `unpack` | `VideoResult` list with scores and duration | Round-trip preserves JSON-compatible dict structure | `pack` then `unpack`; assert equality with `model_dump(mode="json")` |

### Infrastructure — observability (BL-018)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C23 | `test_c23_cached_repository_logs_hit_on_second_call` | `record_cache_hit` / `record_cache_miss` in `CachedDataRepository` | Counting inner repo + in-memory cache | Second call logs `"cache hit"`; metrics show 1 hit, 1 miss | `caplog` at DEBUG on `cache_observability` logger; `get_cache_metrics()` |
| C24 | `test_c24_cached_llm_logs_hit_on_second_call` | `record_cache_hit` in `CachedChatModel` | Counting inner model + in-memory cache | Inner model invoked once; second call logs hit | Assert inner `calls == 1`; caplog + metrics |

### Infrastructure — graceful degradation (BL-012)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C18 | `test_c18_redis_cache_store_degrades_on_unreachable_host` | `RedisCacheStore` miss on connection failure | Unreachable Redis URL `redis://127.0.0.1:1` | `get` returns `None` without raising | Assert `await store.get(...) is None` |
| C08 | `test_c08_create_cache_store_returns_noop_when_disabled` | `create_cache_store` when disabled | `CACHE_ENABLED=false` | Returns `NoOpCacheStore` | Assert type name |

### Documentation — production cache (BL-012)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| DOC01 | Manual: `ENVIRONMENT_SETUP.md` production cache section | BL-012 acceptance criteria | Read committed doc | Documents `CACHE_ENABLED=true`, `REDIS_URL`, Doppler checklist, graceful degradation | Grep/section review — not pytest |

### Builder guard rails (remediation from CODE_REVIEW3)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM07 | `test_llm07_build_chat_model_wraps_with_cache_when_enabled` | `build_chat_model` with shared store | `CACHE_ENABLED=true`, explicit `InMemoryCacheStore` | Returns `CachedChatModel` | Assert type name |

## Deferred (not testable yet)

- `build_document_video_workflow` / `build_mcp_tool_cache` `ValueError` when `cache=None` and enabled — same guard pattern as LLM07b; deferred (low risk; covered by composition-root path in C21)
- `get_document_video_workflow()` MCP consumer — deferred to BL-001
- `build_search_client()` composition-root wiring — deferred per INVESTIGATION3
- BL-015 compression, BL-016 stampede protection — out of scope
- `.env.example` version-controlled production checklist — gitignored; checklist lives in `ENVIRONMENT_SETUP.md` only

## Handoff to implementation

[IMPLEMENTATION5.md](./IMPLEMENTATION5.md)
