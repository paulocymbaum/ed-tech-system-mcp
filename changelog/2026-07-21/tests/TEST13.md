# Test Inventory 13: REFACTOR2 homologation (RF01–RF12, RF21)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [refactor/INVESTIGATION1.md](../refactor/INVESTIGATION1.md), [refactor/IMPLEMENTATION1.md](../refactor/IMPLEMENTATION1.md), [refactor/CODE_REVIEW1.md](../refactor/CODE_REVIEW1.md), [refactor/REFACTOR2.md](../refactor/REFACTOR2.md)

## Scope

Homologate REFACTOR2 implementation — 11 actionable items across entrypoint, application, infrastructure, and interface layers. Prior inventories TEST1–TEST12 remain valid.

| RF | Summary | Layer |
| :--- | :--- | :--- |
| RF01 | Local UI composition-root bootstrap (+ lifespan under reload) | entrypoint, interface |
| RF02 | MCP tool cache singleflight | infrastructure |
| RF03 | Cancel provisional YouTube task on title refinement | application |
| RF04 | Lazy-init `DocumentVideoWorkflow` at composition root | entrypoint, application |
| RF07 | MCP tool cache payload size guard | infrastructure |
| RF08 | LLM cache singleflight | infrastructure |
| RF09 | Memoize compiled graph (shared by run + registry) | application |
| RF10 | Extract `workflow_state_to_run_response` helper | interface |
| RF11 | Map uninitialized workflow to `ResourceNotFoundError` | interface, application |
| RF12 | Read retry policy on derive/merge nodes | application |
| RF21 | Export cache hit-rate at INFO | infrastructure |

## Test catalog

### RF01 — local UI bootstrap (entrypoint + lifespan)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF01a | `test_e06_local_ui_main_bootstraps_application_runtime` | REFACTOR2 RF01; `local_ui_main.main` docstring | Patch bootstrap helpers; call `main()` | `bootstrap_environment` then `bootstrap_application_runtime` before `uvicorn.run` | Call-order list; uvicorn invoked once |
| T-RF01b | `test_local_ui_lifespan_bootstraps_application_runtime` | CODE_REVIEW1 remediation; `create_local_ui_app(bootstrap_runtime=True)` lifespan | TestClient with lifespan; patch bootstrap helpers | Lifespan calls `bootstrap_environment` and `bootstrap_application_runtime` on worker import | Mock assert_called_once; health endpoint 200 |

### RF03 — YouTube cancel on title refinement (application)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF03a | `test_t19c_sequential_video_refetch_when_document_title_differs` | REFACTOR2 RF03; `retrieve_with_videos` | Doc title ≠ query; slow video client counter | Exactly 1 YouTube call; `last_query` = document title | Counter on fake port |
| T-RF03b | `test_t19d_skips_second_video_fetch_when_title_matches_query` | RF03 parallel-preservation branch | Doc title == query | 1 YouTube call; provisional result reused | Counter == 1 |
| T-RF03c | `test_t19b_parallel_io_when_no_documents` | RF03 empty-documents branch | Empty repo; tracking client | Video search starts before doc fetch completes | Timing tracker flag |

### RF02 — MCP tool cache singleflight (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF02 | `test_c36_mcp_tool_cache_parallel_misses_invoke_once` | REFACTOR2 RF02; `run_cache_aside` singleflight | 8 concurrent `get_or_invoke` on cold key | Invoker called once; `cache.set` once | Counter + cache set_calls |

### RF07 — MCP payload size guard (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF07 | `test_c37_mcp_tool_cache_skips_oversize_payload` | REFACTOR2 RF07; `payload_within_cache_limit` | Monkeypatch `MAX_CACHE_PAYLOAD_BYTES=32`; large result | Result returned; `cache.set` skipped; storage empty | set_calls == 0; result equality |

### RF08 — LLM cache singleflight (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF08 | `test_llm04c_cached_chat_model_parallel_misses_invoke_inner_once` | REFACTOR2 RF08; `CachedChatModel._agenerate` | 8 concurrent `_agenerate` on cold key | Inner model called once; `cache.set` once | Stub counter + set_calls |

### RF04 — lazy workflow init (entrypoint/wiring)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF04a | `test_llm06b_initialize_application_runtime_defers_workflow_until_access` | REFACTOR2 RF04; lazy builder pattern | Count `build_document_video_workflow` during init | build_calls == 0 at init; == 1 after `get_document_video_workflow()` | Monkeypatch counter |
| T-RF04b | `test_c21_initialize_application_runtime_creates_single_cache_store` | RF04 context; `ApplicationContext` | `initialize_application_runtime` | `context.document_video_workflow is None` at boot | Assert context field |

### RF09 — graph memoization (application)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF09a | `test_compiled_graph_shared_by_run_and_registry` | REFACTOR2 RF09; `_get_compiled_graph` | Count `build_document_video_graph`; run graph + list workflows | build_count == 1; registry graph is `_get_compiled_graph()` | Counter + object identity |
| T-RF09b | `test_list_registered_workflows_memoizes_compiled_graph` | BL-023 / shared memo | Two list calls | build_count == 1; same list object | Counter (TEST12; still valid) |

### RF10 — workflow response helper (interface)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF10a | `test_t_rf10_workflow_state_to_run_response_maps_state_fields` | REFACTOR2 RF10; `workflow_state_to_run_response` | Construct `DocumentVideoState` dict with docs/videos | `WorkflowRunResponse` fields match state; documents pruned to summaries | Assert public response fields only |
| T-RF10b | `test_t24_run_workflow_returns_graph_counts` | MCP consumer path | Wired workflow; `run_workflow()` | Counts and search_terms from graph state | Integration via public tool |
| T-RF10c | `test_post_run_workflow_returns_response_when_wired` | Local UI consumer path | POST `/api/workflows/.../run` | 200; query/count fields in JSON | HTTP response body |

### RF11 — uninitialized workflow domain error (interface)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF11a | `test_t32_uninitialized_workflow_maps_to_not_found_error` | REFACTOR2 RF11; `error_mapping.py` | `reset_document_video_workflow()`; `find_documents()` | FastMCP `NotFoundError` with init message | pytest.raises on public MCP tool |
| T-RF11b | `test_post_run_workflow_returns_503_when_uninitialized` | RF11 HTTP mapping | POST run without workflow | HTTP 503; detail contains init message | Status code + JSON detail |

### RF12 — read retry on derive/merge (application)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF12 | `test_llm05e_graph_derive_and_merge_nodes_use_read_retry_policy` | REFACTOR2 RF12; `_read_node_retry_policy` | `node_retries=3`; spy `StateGraph.add_node` | derive/merge `max_attempts` == read policy (2), not full node policy (4) | Spy kwargs on public graph build |

### RF21 — cache hit-rate INFO logging (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-RF21 | `test_c38_cache_hit_rate_logged_at_info` | REFACTOR2 RF21; `_maybe_log_hit_rate` | 9 misses + 1 hit via `record_cache_*` | INFO log contains `cache hit-rate operation=mcp_tool` and `hit_rate=` | caplog at INFO |

## Deferred (not testable yet)

- **RF05/RF06** — BL-022 adapter HTTP bodies and Groq timeout kwargs; stubs raise `ResourceNotFoundError` / `NotImplementedError`
- **RF13–RF20** — explicit deferrals in REFACTOR2 (ops, product, BL-022 scope)
- **Production `CACHE_ENABLED=true` deploy** — RF13 ops checklist; not unit-testable
- **Live Redis / Groq / Supabase / YouTube** — external APIs excluded per homologation rules

## Handoff to implementation

[IMPLEMENTATION13.md](./IMPLEMENTATION13.md)
