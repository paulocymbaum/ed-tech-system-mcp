# Implementation 2: Operational config.json and language model registry

**Date:** 2026-07-21
**Layer:** entrypoint
**Investigation:** [INVESTIGATION2.md](./INVESTIGATION2.md)
**Status:** done

## Summary

Add repo-root `config.json` with operational retry/timeout settings, validate via Pydantic at startup, map to an application `WorkflowExecutionConfig` through `wiring.py`, and publish `AVAILABLE_LANGUAGE_MODELS` for future LLM factory use.

## Checklist

- [x] **1.** Create `config.json` with `node_retries`, `workflow_timeout`, `agent_node_timeout`
- [x] **2.** Create `src/mcp_server/operational_config.py` (Pydantic model + loader)
- [x] **3.** Create `src/mcp_server/application/workflow_config.py` (runtime config type + accessor)
- [x] **4.** Create `src/mcp_server/application/llm_models.py` (`AVAILABLE_LANGUAGE_MODELS`)
- [x] **5.** Update `src/mcp_server/wiring.py` to map and initialize runtime config
- [x] **6.** Update `src/mcp_server/main.py` to load operational config at startup
- [x] **7.** Add `tests/test_operational_config.py`
- [x] **8.** Add `tests/test_llm_models.py`
- [x] **9.** Run `uv run ruff check src/` and fix issues
- [x] **10.** Run `uv run mypy src/`
- [x] **11.** Run `uv run pytest`
- [x] **12.** Update investigation/implementation status

## Task details

### 1. config.json

- **File(s):** `config.json`
- **Done when:** JSON contains the three keys; timeout values are seconds; `node_retries` is a count

### 2. operational_config.py

- **File(s):** `src/mcp_server/operational_config.py`
- **Done when:** `OperationalConfig` validates fields; `load_operational_config()` reads repo-root default path

### 5. wiring.py

- **File(s):** `src/mcp_server/wiring.py`
- **Done when:** `initialize_application_runtime()` sets `WorkflowExecutionConfig` from `OperationalConfig`

### 6. main.py

- **File(s):** `src/mcp_server/main.py`
- **Done when:** Startup loads operational config and initializes application runtime before MCP server run

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Remediation (CODE_REVIEW2 warnings)

- [x] **R1.** Document `config.json` in `ENVIRONMENT_SETUP.md` (keys, units, startup failure behavior)
- [x] **R2.** Update `ARCHITECTURE.md` file tree with `config.json`, `operational_config.py`, `workflow_config.py`, `llm_models.py`, `settings.py`, `wiring.py`
- [x] **R3.** Update `AGENTIC_ARCHITECTURE.md` file tree and quick-reference map for the same modules
- [x] **R4.** Add `test_main_startup_loads_operational_config_before_mcp_server` in `tests/test_entrypoint.py`
- [x] **R5.** Run `uv run ruff check src/`
- [x] **R6.** Run `uv run mypy src/`
- [x] **R7.** Run `uv run pytest`
