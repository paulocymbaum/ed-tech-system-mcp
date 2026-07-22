# Test Inventory 12: Memoize UI workflow list + config.json defaults (BL-023, BL-027)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [interface/INVESTIGATION2.md](../interface/INVESTIGATION2.md), [interface/IMPLEMENTATION2.md](../interface/IMPLEMENTATION2.md), [interface/CODE_REVIEW2.md](../interface/CODE_REVIEW2.md)

## Scope

Homologate interface increment 2 — Batch 6:

- **BL-023** — Memoize `list_registered_workflows()` at module level in `application/agent.py`; local UI `/api/workflows` must not recompile LangGraph on every request; `reset_registered_workflows_cache()` for test isolation.
- **BL-027** — Single source of truth for `DEFAULT_WORKFLOW_EXECUTION_CONFIG` via `load_operational_config()` + committed `config.json`; remove hardcoded `3/300/60` duplicates in `workflow_config.py`.

Layers touched: application (primary), interface (consumer). Prior inventories TEST1–TEST11 remain valid.

## Test catalog

### application/agent — workflow list memoization (BL-023)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-A01 | `test_list_registered_workflows_memoizes_compiled_graph` | IMPLEMENTATION2 task 3; `list_registered_workflows` docstring | Monkeypatch counter on `build_document_video_graph`; call list twice | `build_count == 1`; `first is second` (same cached list object) | Counter + object identity; reset cache in teardown |
| T-A02 | `test_reset_registered_workflows_cache_rebuilds_on_next_call` | `reset_registered_workflows_cache` docstring | List → reset → list with build counter | `build_count == 2`; `first is not second` | Counter proves rebuild after reset |
| T-A03 | `test_list_registered_workflows_returns_document_video_discovery_metadata` | `_build_registered_workflows()` field literals | Fresh cache; single list call | One workflow with `id="document-video-discovery"`, name and description from contract | Assert public `RegisteredWorkflow` attributes only |

### interface/local_ui — workflow list endpoint (BL-023 consumer)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-UI01 | `test_list_workflows_returns_langgraph_metadata` | `WorkflowGraphView` schema; `api.py` list route | `GET /api/workflows` via TestClient | 200; `framework == "langgraph"`; start node and `__start__` edge present | Response JSON structure from Pydantic models |

### application/workflow_config — config.json defaults (BL-027)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-WC01 | `test_llm12_default_workflow_execution_config_matches_config_json` | `workflow_config.py` comment; `config.json` | Read repo-root `config.json`; compare to `DEFAULT_WORKFLOW_EXECUTION_CONFIG` | Field parity: `node_retries`, `workflow_timeout_seconds` ← `workflow_timeout`, `agent_node_timeout_seconds` ← `agent_node_timeout` | Expected values from committed JSON file, not literals |
| T-WC02 | `test_o09_build_workflow_execution_config_maps_field_names` | `build_workflow_execution_config` mapping | Custom `OperationalConfig` instance | `workflow_timeout` → `workflow_timeout_seconds`; `agent_node_timeout` → `agent_node_timeout_seconds` | Assert mapped fields on `WorkflowExecutionConfig` |

### application/agent — runtime config fallback (BL-027 consumer)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-WC03 | `test_workflow_timeout_seconds_falls_back_to_config_json_defaults` | `_workflow_runtime_config()` fallback branch | `reset_workflow_execution_config()` (no runtime init) | `workflow_timeout_seconds()` equals `config.json` `workflow_timeout` | Compare to JSON file, not hardcoded constants |

## Deferred (not testable yet)

- **`create_agent()` / `run_document_video_graph()` execution-path caching** — explicitly out of scope per INVESTIGATION2; graph still builds per run invocation
- **`_workflow_index()` view projection caching** — graph compilation memoized; dict rebuild per GET deferred
- **`backlog/BACKLOG.md` BL-023/BL-027 status update** — master agent after homologation
- **Import-time `config.json` missing-file failure** — process/import failure; covered indirectly by `test_o10` / startup contract, not re-tested at `workflow_config` import

## Handoff to implementation

[IMPLEMENTATION12.md](./IMPLEMENTATION12.md)
