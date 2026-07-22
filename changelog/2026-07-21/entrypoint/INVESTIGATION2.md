# Investigation 2: Operational config.json and language model registry

**Date:** 2026-07-21
**Layer:** entrypoint
**Status:** approved

## User request

Create centralized `config.json` defining operational configuration the MCP server must respect:

1. Number of node Retries (node retry count for LangGraph/agent nodes)
2. Workflow Timeout (overall workflow execution timeout)
3. Agent Node Timeout (per-node execution timeout)

Also create a **Python dict** with a list of available language models.

## Architecture alignment

- **Layers touched:** entrypoint (primary — load/validate JSON at startup), application (consume runtime config + model registry)
- **Patterns applied:** Pydantic validation at entrypoint (mirrors `Settings`), settings-to-domain mapping (mirrors `cache_config.py`), composition-root wiring via `wiring.py`, secrets stay in env `Settings` while operational tuning lives in `config.json`
- **Anti-patterns avoided:** No secrets in `config.json`, no `os.environ` in application layer, no global lazy env reads for operational values

## Current state

| Asset | Status |
| :--- | :--- |
| `settings.py` | Present — Pydantic `BaseSettings` for env-backed secrets |
| `infrastructure/cache_config.py` | Present — maps `Settings` → domain `CacheRuleSet` |
| `main.py` | Loads settings at startup; does not load operational JSON |
| `wiring.py` | Wires infrastructure adapters; no workflow timeout/retry config |
| `application/agent.py` | LangGraph skeleton; no retry/timeout consumption yet |
| `config.json` | **Missing** |
| `AVAILABLE_LANGUAGE_MODELS` / `llm_models.py` | **Missing** |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `config.json` with retry/timeout keys | entrypoint | P0 |
| No Pydantic loader for operational config | entrypoint | P0 |
| No application-layer runtime config type | application | P0 |
| Operational values not loaded at startup | entrypoint | P0 |
| No injectable path from wiring → application | entrypoint / application | P1 |
| No language model registry constant | application | P0 |
| No tests for config loading or model registry | tests | P1 |

## Minimal increment

Add repo-root `config.json` with three operational keys (units documented in JSON comments via a `_units` sibling object or module docstring), a Pydantic `OperationalConfig` loader in `operational_config.py`, an application `WorkflowExecutionConfig` dataclass with getter/setter initialized from `wiring.py` at startup, and `AVAILABLE_LANGUAGE_MODELS` in `application/llm_models.py`. Wire `main.py` to load operational config alongside settings. Defer full LLM factory, LangGraph retry policies, and timeout enforcement inside graph nodes.

### Scope (in)

- `config.json` at repo root (`node_retries`, `workflow_timeout`, `agent_node_timeout`)
- `src/mcp_server/operational_config.py` — Pydantic model + `load_operational_config()`
- `src/mcp_server/application/workflow_config.py` — `WorkflowExecutionConfig` + runtime accessor
- `src/mcp_server/application/llm_models.py` — `AVAILABLE_LANGUAGE_MODELS` list of dicts
- `wiring.py` — `build_workflow_execution_config()` + `initialize_application_runtime()`
- `main.py` — load operational config and initialize runtime before server start
- Unit tests for loader validation and model registry shape

### Scope (out / deferred)

- Full `application/llm.py` factory
- Doppler/env overrides for operational values
- LangGraph node retry/timeout enforcement in graph compilation
- UI exposure of config or model list

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `config.json` | create | Canonical operational tuning source at repo root (parallel to `.env`) |
| `src/mcp_server/operational_config.py` | create | Pydantic loader/validator for `config.json` |
| `src/mcp_server/application/workflow_config.py` | create | Application-layer runtime config type + accessor |
| `src/mcp_server/application/llm_models.py` | create | Importable language model registry |
| `src/mcp_server/wiring.py` | modify | Map operational config → application runtime config |
| `src/mcp_server/main.py` | modify | Load operational config at startup |
| `tests/test_operational_config.py` | create | Loader validation and wiring integration |
| `tests/test_llm_models.py` | create | Registry structure contract |

### `config.json` location choice

**Repo root (`config.json`)** — chosen over `config/config.json` because:

- Mirrors `.env` / `.env.example` placement already used by `main.py` (`parents[2]` from `src/mcp_server/`)
- Single obvious path for operators and deployment manifests
- No extra directory scaffolding for one file

## Dependencies & environment

- Runtime deps: none (uses existing `pydantic`)
- Dev deps: none
- Secrets / env vars: unchanged — operational values are not env-backed
- Commands: `uv sync --frozen`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Packaged installs:** `config.json` is resolved relative to repo root, not the wheel — acceptable for this MCP server (run from project root or set explicit path later)
- **Units:** timeouts in seconds (`float` allowed for sub-second future use); `node_retries` is a non-negative integer count

## Handoff to implementation

IMPLEMENTATION2.md should order: `config.json` → `operational_config.py` → `workflow_config.py` → `llm_models.py` → `wiring.py` → `main.py` → tests → ruff/mypy/pytest gates.
