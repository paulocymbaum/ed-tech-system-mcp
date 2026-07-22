# Implementation 1: Groq LLM integration with caching and workflow limits

**Date:** 2026-07-21
**Layer:** application
**Investigation:** [INVESTIGATION1.md](./INVESTIGATION1.md)
**Status:** done

## Summary

Extend cache domain and Settings for LLM completions, add Groq adapter and cached LLM wrapper in infrastructure, implement application-layer `create_chat_model()` with wiring-injected Groq builder, apply LangGraph retry/timeout policies from `WorkflowExecutionConfig`, and verify with focused pytest contracts.

## Checklist

- [x] **1.** Extend `domain/cache.py` with `LLM_COMPLETION` and default rule
- [x] **2.** Extend `settings.py` with Groq/LLM/cache fields
- [x] **3.** Update `infrastructure/cache_config.py` for LLM cache mapping
- [x] **4.** Add `langchain-groq` via `uv add langchain-groq`
- [x] **5.** Create `infrastructure/groq_adapter.py`
- [x] **6.** Create `infrastructure/cached_llm.py`
- [x] **7.** Create `application/llm.py` (factory, builder registration, runtime accessor)
- [x] **8.** Update `application/llm_models.py` with Groq models and resolver
- [x] **9.** Update `application/agent.py` with retry/timeout policies
- [x] **10.** Update `wiring.py` and `main.py` for chat model wiring
- [x] **11.** Update `.env.example` and Doppler bootstrap placeholders
- [x] **12.** Add `tests/test_llm.py` and update `tests/test_llm_models.py`
- [x] **13.** Run `uv run ruff check src/ tests/` and fix issues
- [x] **14.** Run `uv run mypy src/`
- [x] **15.** Run `uv run pytest`
- [x] **16.** Update investigation/implementation status to done

## Task details

### 1. Domain cache extension

- **File(s):** `src/mcp_server/domain/cache.py`
- **Done when:** `CacheOperationType.LLM_COMPLETION` exists with TTL/prefix defaults

### 7. Application LLM factory

- **File(s):** `src/mcp_server/application/llm.py`
- **Done when:** `create_chat_model(settings, model_id?, temperature?)` returns `BaseChatModel` using registered Groq builder; no `os.getenv()`

### 9. Agent graph policies

- **File(s):** `src/mcp_server/application/agent.py`
- **Done when:** Nodes use `RetryPolicy(max_attempts=node_retries+1)` and `timeout=agent_node_timeout_seconds`

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Deviations

- Graph nodes converted to `async def` because LangGraph only supports per-node `timeout` on async nodes.
- `agent.py` uses `_workflow_runtime_config()` with `DEFAULT_WORKFLOW_EXECUTION_CONFIG` when runtime config is not yet initialized (local UI listing before full bootstrap).

## Remediation (CODE_REVIEW1)

- [x] **R1.** Format `application/llm.py` (`ruff format`)
- [x] **R2.** Add `DEFAULT_WORKFLOW_EXECUTION_CONFIG` in `workflow_config.py`; use in `agent.py` fallback
- [x] **R3.** Update `ARCHITECTURE.md` file tree (`llm.py`, `groq_adapter.py`, `cached_llm.py`)
- [x] **R4.** Update `AGENTIC_ARCHITECTURE.md` — `llm.py` status, Groq settings, infra modules
- [x] **R5.** Add Groq/LLM/cache env vars to `ENVIRONMENT_SETUP.md`
