# Code Review 2: Operational config.json and language model registry

**Date:** 2026-07-21
**Layer:** entrypoint
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION2.md](./INVESTIGATION2.md)
- [IMPLEMENTATION2.md](./IMPLEMENTATION2.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `eef9003` | Refactor caching logic and enhance workflow integration *(includes INVESTIGATION2 / IMPLEMENTATION2 deliverables)* |

**Entrypoint2 files introduced in `eef9003`:**

| Path | Role |
| :--- | :--- |
| `config.json` | Repo-root operational tuning |
| `src/mcp_server/operational_config.py` | Pydantic loader |
| `src/mcp_server/application/workflow_config.py` | Application runtime config + accessor |
| `src/mcp_server/application/llm_models.py` | `AVAILABLE_LANGUAGE_MODELS` registry |
| `src/mcp_server/wiring.py` | `build_workflow_execution_config`, `initialize_application_runtime` |
| `src/mcp_server/main.py` | Startup load + initialize |
| `tests/test_operational_config.py` | Loader and wiring tests |
| `tests/test_llm_models.py` | Registry contract tests |

## Summary

INVESTIGATION2 and IMPLEMENTATION2 are delivered: repo-root `config.json`, Pydantic validation at startup, composition-root mapping to `WorkflowExecutionConfig`, and a typed `AVAILABLE_LANGUAGE_MODELS` registry. Layer boundaries are respected — secrets remain in `Settings`, operational values live in JSON, and application code has no `os.environ` reads. All quality gates pass locally (62 tests). Deferred scope (LLM factory, LangGraph retry/timeout enforcement, env overrides) was correctly left out. Verdict is **approve with nits** — documentation drift and a missing `main()` integration test are the main follow-ups, not blockers.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION2 | All scope (in) items delivered. Scope (out) correctly deferred. Units documented via `operational_config.py` module docstring (acceptable alternative to `_units` in JSON). Repo-root path mirrors `.env` resolution (`parents[2]`). |
| IMPLEMENTATION2 | All 12 checklist items checked; status `done` matches code. Verification gates recorded and re-confirmed in this review. |
| ARCHITECTURE.md | Patterns followed: Pydantic validation before application use, composition root in `wiring.py`, secrets vs operational config split. **Drift:** file tree does not list `operational_config.py`, `workflow_config.py`, `llm_models.py`, or `config.json`. |
| AGENTIC_ARCHITECTURE.md | Aligns with planned `llm.py` factory and runtime context populated by `wiring.py`. Global `_runtime_config` is initialized at startup (not lazy env read) — acceptable for this increment but differs from preferred constructor-injection wording for future agent nodes. **Drift:** canonical layout omits new application modules. |
| ENVIRONMENT_SETUP.md | **Drift:** no mention of `config.json`, required keys, or startup failure when the file is missing/invalid. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `config.json` with three keys | Present at repo root with `node_retries: 3`, `workflow_timeout: 300`, `agent_node_timeout: 60` | match |
| `operational_config.py` — Pydantic + loader | `OperationalConfig` with `ge=0` / `gt=0` constraints; `load_operational_config()` + `default_config_path()` | match |
| `workflow_config.py` — dataclass + accessor | Frozen `WorkflowExecutionConfig`; `set_` / `get_` / `reset_` helpers | match |
| `llm_models.py` — model registry | `LanguageModelSpec` TypedDict; 6 models (OpenAI + Anthropic) | match |
| `wiring.py` — map + initialize | `build_workflow_execution_config`, `initialize_application_runtime` | match |
| `main.py` — load at startup | `load_operational_config()` → `initialize_application_runtime()` before `create_mcp_server()` | match |
| `tests/test_operational_config.py` | 6 tests: loader, validation, wiring, uninitialized getter | match |
| `tests/test_llm_models.py` | 4 tests: non-empty, required fields, providers, typing | match |
| Deferred: LLM factory, graph enforcement, env overrides | Not implemented | match (deferred) |
| `config.json` `_units` sibling | Module docstring used instead | partial (acceptable per investigation) |

## Layer review (entrypoint)

### Files reviewed

- `config.json` — three operational keys; no secrets
- `src/mcp_server/operational_config.py` — Pydantic `OperationalConfig`; JSON load from repo root; units in module docstring
- `src/mcp_server/main.py` — bootstrap order: `.env` → `Settings` → operational config → runtime init → MCP server
- `src/mcp_server/wiring.py` — `OperationalConfig` → `WorkflowExecutionConfig` mapping at composition root

### Cross-layer files (INVESTIGATION2 scope)

- `src/mcp_server/application/workflow_config.py` — application runtime view; module-global initialized via `wiring.py` only
- `src/mcp_server/application/llm_models.py` — static registry for future `llm.py` factory; no infrastructure imports
- `tests/test_operational_config.py`, `tests/test_llm_models.py` — contract and wiring coverage

### Architecture & patterns

- Operational config validation mirrors `Settings` pattern (Pydantic at entrypoint, consumed via wiring).
- Secrets stay in `settings.py` / env; `config.json` holds only non-secret tuning.
- `initialize_application_runtime` is the sole writer of `_runtime_config`; tests use `reset_workflow_execution_config()`.
- `get_workflow_execution_config()` and `AVAILABLE_LANGUAGE_MODELS` are not yet consumed by `agent.py` or graph compilation — explicitly deferred.
- No forbidden imports in application modules added by this increment.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (operational config does not bypass domain ports)
- [x] No secrets in source, `config.json`, or changelog

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **`ENVIRONMENT_SETUP.md` omits `config.json`.** Operators have no canonical doc for the three required keys, units, or the fact that a missing/invalid file fails startup. Add a short section parallel to env-var documentation.
- **Canonical architecture docs not updated.** `ARCHITECTURE.md` and `AGENTIC_ARCHITECTURE.md` file trees omit `operational_config.py`, `workflow_config.py`, `llm_models.py`, and `config.json`, creating drift for future agents.
- **No `main()` startup integration test.** `test_operational_config.py` covers the loader and `initialize_application_runtime`, but nothing asserts that `main()` calls `load_operational_config` before `create_mcp_server()`. A mocked `main()` test would lock the bootstrap order.

### Nits (consider)

- **`_settings` still discarded in `main()`.** Pre-existing from increment 1; settings are validated but the instance is unused until adapter wiring consumes it in a later increment.
- **No `config.json.example`.** Unlike `.env.example`, there is no committed template for operators who clone without the default `config.json` values memorized (the committed `config.json` mitigates this).
- **`AVAILABLE_LANGUAGE_MODELS` has no uniqueness check.** Duplicate `id` values would not be caught until a future factory consumes the registry.
- **Increment bundled in `eef9003`.** Operational config ships in the same commit as cache/workflow-ui changes; bisect and blame are harder than a dedicated entrypoint2 commit.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (33 source files) |
| `uv run pytest` | pass (62 tests) |

## Verdict

**approve with nits**

Implementation matches INVESTIGATION2 and IMPLEMENTATION2, respects Clean Architecture layer rules, keeps secrets out of `config.json`, and passes all CI-equivalent gates. No critical or blocking issues. Address documentation drift (`ENVIRONMENT_SETUP.md`, architecture file trees) and add a `main()` bootstrap test when convenient; deferred consumption of workflow limits and the model registry is intentional and documented.
