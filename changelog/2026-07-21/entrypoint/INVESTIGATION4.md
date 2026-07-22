# Investigation 4: Lazy-init LLM and bootstrap logging (BL-004, BL-007)

**Date:** 2026-07-21
**Layer:** entrypoint
**Status:** approved

## User request

Batch 2 — entrypoint startup improvements covering backlog BL-004 (lazy-init LLM at startup) and BL-007 (bootstrap logging from `LOG_LEVEL`). Defer `build_chat_model()` until first `get_chat_model()` access; configure `logging.basicConfig` from `settings.log_level` after `load_settings()` in `main.py`.

## Architecture alignment

- **Layers touched:** entrypoint (`main.py`), application (`llm.py`), wiring (`wiring.py`), tests
- **Patterns applied:** Composition-root lazy factory registration (mirrors existing `register_groq_model_builder`); entrypoint-only logging bootstrap; settings injected at wiring, not read in application
- **Anti-patterns avoided:** No `os.environ` in application layer; no eager Groq client construction at boot; no logging config scattered outside entrypoint

## Current state

| Asset | Status |
| :--- | :--- |
| `wiring.py:217` | Eager `set_chat_model(build_chat_model(settings, cache_store))` on every boot |
| `application/llm.py` | `get_chat_model()` returns pre-set `_runtime_chat_model`; no lazy path |
| `main.py` | No `logging.basicConfig`; `LOG_LEVEL` field exists in `Settings` but unused |
| `tests/test_llm.py` | `test_llm06` expects model wired immediately after `initialize_application_runtime` |
| `tests/test_entrypoint.py` | No boot-without-Groq-key test; no log-level test |
| Performance audit P05 | Flagged eager LLM wiring at every MCP boot |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Groq model built at boot even when no LLM tool invoked | entrypoint / wiring | P1 (BL-004) |
| `LOG_LEVEL` not applied to root logger | entrypoint | P1 (BL-007) |
| No test proving health-check-only boot without `GROQ_API_KEY` | tests | P1 (BL-004) |
| No test asserting log level from env | tests | P1 (BL-007) |

## Minimal increment

Register a chat-model builder callback from `wiring.py` into `application/llm.py`. Store `settings` + shared `cache_store` at composition root via `configure_lazy_chat_model()`; build on first `get_chat_model()` call. Remove eager `build_chat_model()` from `initialize_application_runtime()`. Add `configure_logging(settings)` in `main.py` after `load_settings()`. Update `test_llm06` for deferred semantics; add entrypoint tests for no-Groq boot and DEBUG log level. Document `LOG_LEVEL` consumption in `ENVIRONMENT_SETUP.md` startup order.

### Scope (in)

- Lazy chat model factory in `llm.py` + wiring registration
- Remove eager LLM build from `initialize_application_runtime`
- `configure_logging()` in `main.py`
- Entrypoint and LLM test updates
- `ENVIRONMENT_SETUP.md` startup-order note for `LOG_LEVEL`
- Cold-start improvement note in `IMPLEMENTATION4.md`

### Scope (out / deferred)

- Agent graph nodes invoking `get_chat_model()` (still deferred from prior increments)
- Structured logging / JSON log format
- `BACKLOG.md` updates (master handles after homologation)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/application/llm.py` | modify | Lazy factory, `configure_lazy_chat_model`, deferred `get_chat_model` build |
| `src/mcp_server/wiring.py` | modify | Register builder; configure lazy deps; remove eager `set_chat_model` |
| `src/mcp_server/main.py` | modify | `configure_logging(settings)` after `load_settings()` |
| `tests/test_llm.py` | modify | Update `test_llm06` for lazy-init semantics |
| `tests/test_entrypoint.py` | modify | Boot without Groq key; log level applied |
| `ENVIRONMENT_SETUP.md` | modify | Document `LOG_LEVEL` consumed at boot |

## Dependencies & environment

- Runtime deps: unchanged
- Dev deps: unchanged
- Secrets / env vars: `GROQ_API_KEY` optional at boot (required only on first `get_chat_model()`)
- Commands: `uv sync --frozen`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Thread safety:** Single-process MCP server; no concurrent lazy-init concern for this increment
- **Test isolation:** `reset_chat_model()` must clear lazy config to avoid cross-test leakage
- **Invalid LOG_LEVEL:** Fall back to `logging.INFO` when string is unrecognized

## Handoff to implementation

`IMPLEMENTATION4.md` should order: application (`llm.py`) → wiring → entrypoint (`main.py`) → tests → lint/type/test gates. Include informal cold-start note after verification.
