# Implementation 4: Lazy-init LLM and bootstrap logging (BL-004, BL-007)

**Date:** 2026-07-21
**Layer:** entrypoint
**Investigation:** [INVESTIGATION4.md](./INVESTIGATION4.md)
**Status:** done

## Summary

Deferred chat model construction until first `get_chat_model()` by registering `build_chat_model` as a lazy factory in the application layer and storing settings + cache store at the composition root via `configure_lazy_chat_model()`. Configured root logging from `settings.log_level` in `main.py` immediately after settings validation. Verified with updated LLM test and new entrypoint tests.

## Checklist

- [x] **1.** BL-004: Add lazy factory (`register_chat_model_builder`, `configure_lazy_chat_model`, deferred `get_chat_model`) in `llm.py`
- [x] **2.** BL-004: Register builder and remove eager `set_chat_model(build_chat_model(...))` in `wiring.py`
- [x] **3.** BL-007: Add `configure_logging(settings)` in `main.py` after `load_settings()`
- [x] **4.** BL-004: Update `test_llm06` for lazy-init semantics
- [x] **5.** BL-004: Add entrypoint test — `main()` boot without `GROQ_API_KEY` (health-check-only path)
- [x] **6.** BL-007: Add entrypoint test asserting `LOG_LEVEL=DEBUG` applies root log level
- [x] **7.** BL-007: Update `ENVIRONMENT_SETUP.md` startup order for `LOG_LEVEL`
- [x] **8.** Run `uv run ruff check src/` and fix issues
- [x] **9.** Run `uv run mypy src/`
- [x] **10.** Run `uv run pytest`
- [x] **11.** Update investigation status; mark implementation done; add cold-start note

## Task details

### 1. Lazy factory (BL-004)

- **File(s):** `application/llm.py`
- **Done when:** `get_chat_model()` builds via registered builder on first access; `reset_chat_model()` clears lazy state

### 2. Wiring (BL-004)

- **File(s):** `wiring.py`
- **Done when:** `initialize_application_runtime` calls `configure_lazy_chat_model(settings, cache_store)` only; no eager Groq build

### 3. Logging bootstrap (BL-007)

- **File(s):** `main.py`
- **Done when:** `logging.basicConfig(level=...)` runs after `load_settings()` with string-to-level mapping

### 5. Boot without Groq (BL-004)

- **File(s):** `tests/test_entrypoint.py`
- **Done when:** Real `initialize_application_runtime` path runs; `create_mcp_server` mocked; no `GROQ_API_KEY`; `main()` completes

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Cold-start note (BL-004)

Boot no longer calls `build_chat_model()` / Groq client construction during `initialize_application_runtime()`. For health-check-only MCP sessions (no agent or LLM tool invocation), startup skips LangChain model wiring and `GROQ_API_KEY` validation entirely. LLM cost is paid on first `get_chat_model()` access — typically when an agent or reasoning path runs. Informal expectation: faster cold start for transports that only register tools and serve non-LLM requests.

## Verification results

| Gate | Result |
| :--- | :--- |
| `uv run ruff check src/` | All checks passed |
| `uv run mypy src/` | Success: no issues found in 39 source files |
| `uv run pytest` | 107 passed (remediation: +2 entrypoint logging tests) |

## Remediation checklist (CODE_REVIEW4)

- [x] **R1.** Add `test_e04_configure_logging_falls_back_to_info_for_invalid_level` — invalid `LOG_LEVEL` falls back to `logging.INFO`
- [x] **R2.** Add `test_e05_configure_logging_maps_log_level_case_insensitively` — e.g. `LOG_LEVEL=warning` → `logging.WARNING`
- [ ] **R3.** *(Deferred)* Commit increment 4 — procedural; master/user handles commits
- [x] **R4.** Re-run `uv run ruff check src/`
- [x] **R5.** Re-run `uv run mypy src/`
- [x] **R6.** Re-run `uv run pytest`
