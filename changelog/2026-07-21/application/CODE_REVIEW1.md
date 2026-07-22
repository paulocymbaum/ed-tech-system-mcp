# Code Review 1: Groq LLM integration with caching and workflow limits

**Date:** 2026-07-21
**Layer:** application
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `eef9003` | Refactor caching logic and enhance workflow integration *(includes application1 deliverables — uncommitted working tree)* |

**Application1 files introduced or modified:**

| Path | Role |
| :--- | :--- |
| `src/mcp_server/application/llm.py` | Chat model factory, Groq builder registration, runtime accessor |
| `src/mcp_server/application/llm_models.py` | Groq models + `resolve_language_model()` |
| `src/mcp_server/application/agent.py` | LangGraph retry/timeout policies, async nodes, workflow timeout helper |
| `src/mcp_server/infrastructure/groq_adapter.py` | `build_groq_chat_model()` via `langchain-groq` |
| `src/mcp_server/infrastructure/cached_llm.py` | `CachedChatModel` cache-aside wrapper |
| `src/mcp_server/domain/cache.py` | `LLM_COMPLETION` operation + default rule |
| `src/mcp_server/infrastructure/cache_config.py` | LLM cache settings mapping |
| `src/mcp_server/settings.py` | `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, LLM cache fields |
| `src/mcp_server/wiring.py` | `build_chat_model()`, extended `initialize_application_runtime()` |
| `src/mcp_server/main.py` | Passes `Settings` to runtime init |
| `.env.example` | Groq/LLM/cache placeholders |
| `scripts/doppler/bootstrap-from-env-example.sh` | Doppler placeholders |
| `pyproject.toml` / `uv.lock` | `langchain-groq` dependency |
| `tests/test_llm.py` | 8 LLM/cache/agent policy contract tests |
| `tests/test_llm_models.py` | Updated provider assertion for Groq |
| `tests/test_entrypoint.py` | Updated `initialize_application_runtime` signature mock |

## Summary

INVESTIGATION1 and IMPLEMENTATION1 are delivered: Groq-first `create_chat_model()` with wiring-injected builder, `CachedChatModel` cache-aside on async completions, LangGraph node `RetryPolicy` and per-node `timeout` from `WorkflowExecutionConfig`, and startup wiring via `initialize_application_runtime(operational, settings)`. Layer boundaries are respected — application never imports infrastructure directly; secrets stay in `Settings` as `SecretStr`. All quality gates pass except `ruff format --check` on `llm.py`. Verdict is **approve with nits** — documentation drift and a hardcoded config fallback are the main follow-ups, not blockers.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | All scope (in) items delivered. Scope (out) correctly deferred. Async-only LLM caching and async graph nodes documented as deviations. |
| IMPLEMENTATION1 | All 16 checklist items checked; status `done` matches code. Deviations section documents async nodes and `_workflow_runtime_config()` fallback. |
| ARCHITECTURE.md | Patterns followed: factory in application, adapter in infrastructure, composition root in `wiring.py`. **Drift:** file tree omits `llm.py`, `groq_adapter.py`, `cached_llm.py`. |
| AGENTIC_ARCHITECTURE.md | LLM factory and injected chat model align with planned design. **Drift:** `llm.py` still marked 📋 planned; no `GROQ_API_KEY` in settings table; infra modules missing from file map. |
| ENVIRONMENT_SETUP.md | **Drift:** no documentation for `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, or `CACHE_TTL_LLM_COMPLETION`. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `application/llm.py` — factory + builder registration | `create_chat_model()`, `register_groq_model_builder()`, `get_chat_model()` | match |
| `llm_models.py` — Groq registry entries | 5 Groq models + `resolve_language_model()` | match |
| `agent.py` — retry/timeout from config | `RetryPolicy(max_attempts=node_retries+1)`, per-node `timeout` | match |
| `settings.py` — Groq/LLM/cache fields | `groq_api_key`, `llm_model`, `llm_temperature`, LLM cache TTL/prefix | match |
| `wiring.py` — `build_chat_model()` + runtime init | Registers builder, wraps with `CachedChatModel` when enabled | match |
| `groq_adapter.py` — Groq adapter | `build_groq_chat_model()` via `ChatGroq` | match |
| `cached_llm.py` — cache-aside wrapper | `CachedChatModel` on `_agenerate` only | match (documented) |
| `domain/cache.py` — `LLM_COMPLETION` | Operation + 3600s TTL, `llm` prefix | match |
| `langchain-groq` dependency | Added via `uv add` | match |
| `.env.example` + Doppler bootstrap | Groq/LLM placeholders | match |
| `tests/test_llm.py` | 8 behavior-focused tests | match |
| Deferred: OpenAI/Anthropic factory | `ValueError` for unsupported providers | match (deferred) |
| Deferred: graph nodes invoke LLM | `get_chat_model()` wired but not consumed by nodes | match (deferred) |

## Layer review (application)

### Files reviewed

- `src/mcp_server/application/llm.py` — factory with `LLMSettings` protocol; Groq builder injected from wiring; no `os.getenv()`
- `src/mcp_server/application/llm_models.py` — Groq models prepended; `resolve_language_model()` raises on unknown id
- `src/mcp_server/application/agent.py` — async nodes with retry/timeout; `_workflow_runtime_config()` fallback; `ainvoke_with_workflow_timeout()` helper

### Cross-layer files (INVESTIGATION1 scope)

- `src/mcp_server/infrastructure/groq_adapter.py` — thin `ChatGroq` wrapper; accepts `SecretStr` api_key
- `src/mcp_server/infrastructure/cached_llm.py` — cache-aside on async path; sync `_generate` passes through
- `src/mcp_server/wiring.py` — sole registrar of Groq builder; builds cached model at startup
- `src/mcp_server/settings.py` — `SecretStr` for `GROQ_API_KEY`; LLM defaults sensible
- `tests/test_llm.py` — factory, cache, agent policy, wiring contracts

### Architecture & patterns

- Application layer depends on LangChain primitives and domain cache types only — no infrastructure imports in `llm.py`.
- Groq adapter lives in infrastructure; wiring registers builder via `register_groq_model_builder()`.
- `CachedChatModel` follows existing cache-aside pattern (`build_cache_key`, `CacheRuleSet`, `ICacheStore`).
- LangGraph nodes converted to `async def` — required for per-node `timeout` support.
- Global runtime accessors (`_groq_model_builder`, `_runtime_chat_model`) mirror existing `workflow_config` pattern.
- `get_chat_model()` is initialized at startup but graph skeleton nodes do not yet invoke it — acceptable for this increment.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected
- [x] No secrets in source, changelog, or `.env.example` values

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **`AGENTIC_ARCHITECTURE.md` and `ARCHITECTURE.md` not updated.** File trees and status snapshots still mark `llm.py` as planned; omit `groq_adapter.py`, `cached_llm.py`, and Groq settings. Future agents will misread layer state.
- **`ENVIRONMENT_SETUP.md` omits Groq/LLM env vars.** No canonical doc for `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, or `CACHE_TTL_LLM_COMPLETION` / `CACHE_KEY_PREFIX_LLM`.
- **`_workflow_runtime_config()` hardcodes fallback defaults.** `agent.py` duplicates `config.json` values (3/300/60) instead of loading from `operational_config.py` or a shared constant — risk of drift if `config.json` changes.
- **`ruff format --check` fails on `llm.py`.** Formatting not applied; CI format gate would fail.

### Nits (consider)

- **`get_chat_model()` not consumed by graph nodes yet.** Wired at startup; `_derive_search_terms` still rule-based. Intentional deferral but worth tracking for next increment.
- **`CachedChatModel._generate` bypasses cache.** Documented in investigation; sync path acceptable for MCP async-first usage.
- **`build_chat_model()` re-registers Groq builder on every call.** Harmless at startup but idempotent registration would be cleaner.
- **No test for unsupported provider path.** `create_chat_model` with OpenAI model id raises `ValueError` — not cataloged in tests yet.
- **No test for unknown model id in `resolve_language_model`.** Raises `ValueError` — gap for homologation.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/ tests/` | pass |
| `uv run ruff format --check src/ tests/` | **fail** — `llm.py` needs reformat |
| `uv run mypy src/` | pass (36 source files) |
| `uv run pytest` | pass (77 tests) |

## Verdict

**approve with nits**

Implementation matches INVESTIGATION1 and IMPLEMENTATION1, respects Clean Architecture layer rules, keeps secrets in Settings/Doppler, and passes ruff lint, mypy, and pytest. Address documentation drift, format `llm.py`, and replace hardcoded config fallback when convenient. Deferred OpenAI/Anthropic factory paths and LLM consumption in graph nodes are intentional and documented.
