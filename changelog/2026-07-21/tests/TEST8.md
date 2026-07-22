# Test Inventory 8: Lazy-init LLM and bootstrap logging (BL-004, BL-007)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [entrypoint/INVESTIGATION4.md](../entrypoint/INVESTIGATION4.md), [entrypoint/IMPLEMENTATION4.md](../entrypoint/IMPLEMENTATION4.md), [entrypoint/CODE_REVIEW4.md](../entrypoint/CODE_REVIEW4.md)

## Scope

Homologate entrypoint increment 4 — Batch 2 startup improvements:

- **BL-004** — Lazy-init LLM via `configure_lazy_chat_model()` + deferred `get_chat_model()`; no eager `build_chat_model()` at boot; health-check-only boot without `GROQ_API_KEY`
- **BL-007** — `configure_logging(settings)` in `main.py` after `load_settings()`; `LOG_LEVEL` string mapping with `INFO` fallback and case-insensitivity

Layers touched: entrypoint (`main.py`), application (`llm.py`), wiring (`wiring.py`), tests. Prior inventories TEST1–TEST7 remain valid.

## Test catalog

### Application — lazy chat model factory (BL-004)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ENT04a | `test_llm06_initialize_application_runtime_defers_chat_model_until_access` | INVESTIGATION4: `get_chat_model()` builds on first access; wiring removes eager build | Real `initialize_application_runtime` with counting `build_chat_model` monkeypatch | `build_calls == 0` after init; `build_calls == 1` after `get_chat_model()`; model non-None | Count builder invocations; assert deferred then built |
| ENT04b | `test_e02_main_boots_without_groq_key_when_llm_not_invoked` | INVESTIGATION4: `GROQ_API_KEY` optional at boot | `APP_ENV=ci`, required Supabase env, no `GROQ_API_KEY`; mock `create_mcp_server` only | `main()` completes; `server.run()` called once | Black-box boot; no patch on runtime init |
| ENT04c | `test_llm08_set_chat_model_runtime_accessor` | `set_chat_model` / `get_chat_model` public API | `set_chat_model(StubChatModel())` | `get_chat_model()` returns same instance without invoking builder | Assert identity; no lazy build required |

### Entrypoint — startup sequence (BL-007)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ENT07a | `test_e01_main_startup_loads_operational_config_before_mcp_server` | `main.py` startup order: `configure_logging` after `load_settings` | Patch full startup chain | Call order includes `configure_logging` between `load_settings` and `load_operational_config` | Track call-order list |

### Entrypoint — logging bootstrap (BL-007)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ENT07b | `test_e03_configure_logging_applies_log_level_from_settings` | `configure_logging` + `Settings.log_level` | `LOG_LEVEL=DEBUG` via `load_settings()` | Root logger level is `logging.DEBUG` | `logging.getLogger().level` after `configure_logging` |
| ENT07c | `test_e04_configure_logging_falls_back_to_info_for_invalid_level` | INVESTIGATION4 risk: unrecognized string → `INFO` | `LOG_LEVEL=NOT_A_LEVEL` | Root logger level is `logging.INFO` | Assert fallback level, not input string |
| ENT07d | `test_e05_configure_logging_maps_log_level_case_insensitively` | `configure_logging` uses `.upper()` on level name | `LOG_LEVEL=warning` | Root logger level is `logging.WARNING` | Map lowercase env to stdlib constant |

### Wiring — composition root registration (BL-004)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ENT04a | `test_llm06_initialize_application_runtime_defers_chat_model_until_access` | `wiring.initialize_application_runtime` calls `configure_lazy_chat_model` only | Same as ENT04a | No `build_chat_model` during init | Shared test with application layer |

## Deferred (not testable yet)

- **Agent graph `get_chat_model()` usage** — agent nodes do not invoke LLM yet (prior increments)
- **Structured / JSON logging** — out of scope per INVESTIGATION4
- **`get_chat_model()` returns `None` when lazy deps unset** — observable but not a documented backlog contract; covered indirectly by autouse `reset_chat_model()` isolation
- **Second `get_chat_model()` call idempotency** — implied by lazy singleton; ENT04a proves single build on first access
- **`ENVIRONMENT_SETUP.md` startup-order note** — documentation-only; not unit-testable
- **`BACKLOG.md` updates** — procedural; master handles post-homologation

## Handoff to implementation

[IMPLEMENTATION8.md](./IMPLEMENTATION8.md)
