# Homologation Report

**Date:** 2026-07-21
**Test inventory:** [TEST13.md](./TEST13.md) (REFACTOR2), [TEST14.md](./TEST14.md) (LLM routing)
**Implementation:** [IMPLEMENTATION13.md](./IMPLEMENTATION13.md), [IMPLEMENTATION14.md](./IMPLEMENTATION14.md), [../application/IMPLEMENTATION3.md](../application/IMPLEMENTATION3.md)
**Status:** final

## Summary

All 20 cataloged test mappings for REFACTOR2 (11 RF items: RF01, RF03, RF02, RF04, RF07, RF08, RF09, RF10, RF11, RF12, RF21) pass. 19 mappings use tests delivered during refactor IMPLEMENTATION1; one unit test (`test_t_rf10_workflow_state_to_run_response_maps_state_fields`) was added for RF10 helper contract coverage.

**LLM routing layer (TEST14 / application IMPLEMENTATION3):** 9 cataloged tests (`test_llm13`–`test_llm20`, `test_llm17b`) cover complexity tiers, failure fallback, token-limit deactivation (domain helper + router integration), token-limit classifier, debounce (async + sync), free-model registry defaults, and composition-root wiring through `RoutingChatModel`. CODE_REVIEW3 remediation verified: per-call temperature via `router.set_temperature` (`test_llm02`), `token_limit_deactivation_until()` wired in router, sync debounce path (`test_llm17b`). LLM-focused suite: **34 passed** in `tests/test_llm.py` + `tests/test_llm_models.py`. Full suite: **178 passed**, 7 skipped. Prior inventories TEST1–TEST13 remain valid.

## Coverage matrix

| TEST ID | Test function | Result | Notes |
| :--- | :--- | :--- | :--- |
| **RF01 — local UI bootstrap** | | | |
| T-RF01a | `test_e06_local_ui_main_bootstraps_application_runtime` | pass | Bootstrap order before uvicorn |
| T-RF01b | `test_local_ui_lifespan_bootstraps_application_runtime` | pass | Reload worker lifespan hook |
| **RF03 — YouTube cancel on refinement** | | | |
| T-RF03a | `test_t19c_sequential_video_refetch_when_document_title_differs` | pass | 1 YouTube call when title differs |
| T-RF03b | `test_t19d_skips_second_video_fetch_when_title_matches_query` | pass | Provisional result reused |
| T-RF03c | `test_t19b_parallel_io_when_no_documents` | pass | Parallel IO preserved for empty docs |
| **RF02 — MCP cache singleflight** | | | |
| T-RF02 | `test_c36_mcp_tool_cache_parallel_misses_invoke_once` | pass | 8 concurrent misses → 1 invoke |
| **RF07 — MCP payload guard** | | | |
| T-RF07 | `test_c37_mcp_tool_cache_skips_oversize_payload` | pass | Oversize skips set; result returned |
| **RF08 — LLM cache singleflight** | | | |
| T-RF08 | `test_llm04c_cached_chat_model_parallel_misses_invoke_inner_once` | pass | 8 concurrent misses → 1 inner call |
| **RF04 — lazy workflow** | | | |
| T-RF04a | `test_llm06b_initialize_application_runtime_defers_workflow_until_access` | pass | No build at init |
| T-RF04b | `test_c21_initialize_application_runtime_creates_single_cache_store` | pass | `document_video_workflow is None` at boot |
| **RF09 — graph memoization** | | | |
| T-RF09a | `test_compiled_graph_shared_by_run_and_registry` | pass | Single compile for run + registry |
| T-RF09b | `test_list_registered_workflows_memoizes_compiled_graph` | pass | List memoization (TEST12 overlap) |
| **RF10 — response helper** | | | |
| T-RF10a | `test_t_rf10_workflow_state_to_run_response_maps_state_fields` | pass | Direct helper contract |
| T-RF10b | `test_t24_run_workflow_returns_graph_counts` | pass | MCP consumer path |
| T-RF10c | `test_post_run_workflow_returns_response_when_wired` | pass | Local UI consumer path |
| **RF11 — domain error mapping** | | | |
| T-RF11a | `test_t32_uninitialized_workflow_maps_to_not_found_error` | pass | MCP NotFoundError |
| T-RF11b | `test_post_run_workflow_returns_503_when_uninitialized` | pass | HTTP 503 |
| **RF12 — read retry policy** | | | |
| T-RF12 | `test_llm05e_graph_derive_and_merge_nodes_use_read_retry_policy` | pass | derive/merge max_attempts == 2 |
| **RF21 — cache hit-rate INFO** | | | |
| T-RF21 | `test_c38_cache_hit_rate_logged_at_info` | pass | INFO log with hit_rate |

### LLM routing (TEST14 / application IMPLEMENTATION3)

| TEST ID | Test function | Result | Notes |
| :--- | :--- | :--- | :--- |
| T-LLM13 | `test_llm13_router_maps_complexity_to_model_tiers` | pass | Complexity 1/2/3 → tiered Groq ids |
| T-LLM14 | `test_llm14_router_falls_back_on_provider_failure` | pass | Primary failure → next model |
| T-LLM15 | `test_llm15_token_limit_error_deactivates_model_for_three_hours` | pass | 3 h registry cooldown via domain helper |
| T-LLM16 | `test_llm16_is_token_limit_error_detects_context_length` | pass | Token-limit classifier |
| T-LLM17 | `test_llm17_debounce_gate_spaces_async_calls` | pass | Configurable async debounce |
| T-LLM17b | `test_llm17b_debounce_gate_spaces_sync_calls` | pass | Sync debounce for `router.generate` |
| T-LLM18 | `test_llm18_groq_registry_marks_only_known_free_models_active` | pass | Free active; paid inactive |
| T-LLM19 | `test_llm19_token_limit_deactivation_until_is_three_hours` | pass | Domain cooldown helper |
| T-LLM20 | `test_llm20_build_chat_model_returns_routing_model` | pass | No direct ChatGroq bypass |

## Verification commands

| Command | Result | Output summary |
| :--- | :--- | :--- |
| `uv run ruff check src/ tests/` | fail | 8 pre-existing E501 line-length violations in `test_architecture_lint.py`, `test_hooks.py`, `test_secrets_homologation.py` (unrelated to routing) |
| `uv run pytest -v` | pass | 178 passed, 7 skipped |
| `uv run pytest tests/test_llm.py tests/test_llm_models.py -v` | pass | 34 passed |

## Gaps and deferrals

- **RF05/RF06 (BL-022)** — adapter HTTP bodies and Groq timeout kwargs; stubs remain; covered by `test_infrastructure_stubs.py`, not happy-path integration
- **RF13–RF20** — explicit REFACTOR2 deferrals (ops, product, BL-022)
- **Production deploy `CACHE_ENABLED=true`** — RF13 ops checklist; not unit-testable
- **OpenAI/Anthropic routing** — static registry only; deferred per IMPLEMENTATION3
- **Redis-backed Groq registry persistence** — in-process registry only
- **Live Groq catalog HTTP** — unit tests use fakes/monkeypatch; no integration test against `/v1/models`
- **`reset_compiled_graph_cache()` test isolation** — exercised in `test_compiled_graph_shared_by_run_and_registry` teardown; no dedicated reset-rebuild test (acceptable; RF09a covers shared memo contract)
- **Ruff E501 in unrelated test files** — pre-existing; not introduced by routing increment

## Verdict

**homologated**
