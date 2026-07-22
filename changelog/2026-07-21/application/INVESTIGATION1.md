# Investigation 1: Groq LLM integration with caching and workflow limits

**Date:** 2026-07-21
**Layer:** application
**Status:** done

## User request

Implement a layer to integrate Groq models into LangGraph nodes with retries respecting operational config (`config.json` → `WorkflowExecutionConfig`), secrets loaded via Doppler (`GROQ_API_KEY` in Settings), and caching for external integrations (extend existing `ICacheStore` / cache-aside pattern).

## Architecture alignment

- **Layers touched:** application (primary — `llm.py`, `agent.py`, model registry), entrypoint (`settings.py`, `wiring.py`), infrastructure (`groq_adapter.py`, `cached_llm.py`), domain (`CacheOperationType` extension), tests
- **Patterns applied:** LLM factory in application with provider builder registered from wiring; Groq adapter in infrastructure; cache-aside wrapper for LLM completions; `WorkflowExecutionConfig` consumed in graph node policies; `SecretStr` credentials from Settings only at entrypoint/wiring
- **Anti-patterns avoided:** No `os.getenv()` in application; no direct infrastructure imports in application (builder injection via `register_groq_model_builder`); no secrets in repo; OpenAI/Anthropic paths deferred

## Current state

| Asset | Status |
| :--- | :--- |
| `application/llm_models.py` | OpenAI + Anthropic registry only; no Groq models |
| `application/llm.py` | **Missing** |
| `application/agent.py` | LangGraph skeleton; no retry/timeout from `WorkflowExecutionConfig` |
| `application/workflow_config.py` | Runtime config getter/setter initialized at startup |
| `settings.py` | No `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, or LLM cache TTL/prefix fields |
| `wiring.py` | Wires ports/workflows/cache; no chat model |
| `domain/cache.py` | Four operation types; no LLM completion type |
| `infrastructure/cached_adapters.py` | Cache-aside for repository/search/video ports |
| `langchain-groq` | **Not in** `pyproject.toml` |
| `.env.example` / Doppler bootstrap | No Groq or LLM placeholders |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `create_chat_model` factory | application | P0 |
| No Groq models in registry | application | P0 |
| No `GROQ_API_KEY` / LLM settings | entrypoint | P0 |
| No wiring for chat model + cache wrapper | entrypoint | P0 |
| No LangGraph retry/timeout on nodes | application | P0 |
| No `LLM_COMPLETION` cache operation | domain | P0 |
| No cached LLM wrapper | infrastructure | P0 |
| No `langchain-groq` dependency | entrypoint | P0 |
| No tests for LLM factory/cache/graph policies | tests | P1 |

## Minimal increment

Add Groq-first LLM stack: extend Settings and `.env.example`, register Groq models, implement `create_chat_model()` with infrastructure builder injection from wiring, wrap completions in `CachedChatModel` when `CACHE_ENABLED`, apply LangGraph `RetryPolicy` and per-node `timeout` from `get_workflow_execution_config()` in `agent.py`, and initialize chat model in `initialize_application_runtime`. Defer OpenAI/Anthropic factory paths, SQL agent graphs, LangChain `@tool` wrappers, and MCP model-selection surface.

### Scope (in)

- `application/llm.py` — factory, Groq builder registration, runtime chat model accessor
- `application/llm_models.py` — Groq model entries + `resolve_language_model()`
- `application/agent.py` — node `retry_policy` + `timeout`; workflow invoke timeout helper
- `settings.py` — Groq key, LLM model/temperature, LLM cache TTL/prefix
- `wiring.py` — `build_chat_model()`, extend `initialize_application_runtime(settings)`
- `infrastructure/groq_adapter.py` — `build_groq_chat_model()`
- `infrastructure/cached_llm.py` — `CachedChatModel` cache-aside wrapper
- `domain/cache.py` — `LLM_COMPLETION` operation + default rule
- `infrastructure/cache_config.py` — map new Settings fields
- `pyproject.toml` — `langchain-groq` via `uv add`
- `.env.example`, `scripts/doppler/bootstrap-from-env-example.sh` — placeholders
- `tests/test_llm.py` — factory, cache, agent policies

### Scope (out / deferred)

- OpenAI/Anthropic `create_chat_model` implementations
- SQL agent graph with LLM
- `langchain_tools.py` wrappers
- Parameter builder LLM enrichment
- Env/Doppler overrides for `config.json` operational values
- MCP tool surface for model selection

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/application/llm.py` | create | Chat model factory + runtime accessor |
| `src/mcp_server/application/llm_models.py` | modify | Groq registry entries + resolver |
| `src/mcp_server/application/agent.py` | modify | Retry/timeout from workflow config |
| `src/mcp_server/settings.py` | modify | Groq + LLM + cache fields |
| `src/mcp_server/wiring.py` | modify | Build/register/inject chat model |
| `src/mcp_server/main.py` | modify | Pass settings to runtime init |
| `src/mcp_server/infrastructure/groq_adapter.py` | create | Groq ChatGroq adapter |
| `src/mcp_server/infrastructure/cached_llm.py` | create | LLM completion cache-aside |
| `src/mcp_server/domain/cache.py` | modify | `LLM_COMPLETION` operation |
| `src/mcp_server/infrastructure/cache_config.py` | modify | LLM cache settings mapping |
| `pyproject.toml` / `uv.lock` | modify | Add `langchain-groq` |
| `.env.example` | modify | Groq/LLM/cache placeholders |
| `scripts/doppler/bootstrap-from-env-example.sh` | modify | Doppler placeholders |
| `tests/test_llm.py` | create | Behavior contracts |
| `tests/test_llm_models.py` | modify | Assert Groq provider present |

## Dependencies & environment

- Runtime deps: `langchain-groq` (via `uv add langchain-groq`)
- Dev deps: unchanged
- Secrets / env vars: `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, `CACHE_TTL_LLM_COMPLETION`, `CACHE_KEY_PREFIX_LLM`
- Commands: `uv sync --frozen`, `uv run ruff check src/ tests/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Sync LLM invoke + async cache:** `CachedChatModel` caches on async path (`_agenerate`); sync `_generate` delegates to inner without cache to avoid event-loop nesting — acceptable for MCP async-first usage
- **Groq key optional at Settings load:** factory raises clear error when Groq model selected without key; tests use stub `BaseChatModel`
- **Workflow timeout:** applied via `asyncio.wait_for` helper at invoke time (LangGraph `compile()` has no global timeout knob)

## Handoff to implementation

IMPLEMENTATION1.md should order: domain cache type → settings → groq adapter → cached LLM → application llm/llm_models/agent → wiring/main → env/bootstrap → tests → ruff/mypy/pytest gates.
