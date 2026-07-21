# Investigation 1: Environment bootstrap and architecture scaffold

**Date:** 2026-07-21
**Layer:** entrypoint
**Status:** approved

## User request

Set up the Python environment and scaffold the file structure according to `ARCHITECTURE.md` and `ENVIRONMENT_SETUP.md`.

## Architecture alignment

- **Layers touched:** domain, application, interface, infrastructure, entrypoint (all layers receive scaffold stubs; entrypoint owns bootstrap)
- **Patterns applied:** Clean Architecture layer layout, Ports & Adapters stubs in domain/infrastructure, Pydantic Settings at entrypoint, single `load_dotenv()` call site
- **Anti-patterns avoided:** No business logic in MCP tools, no `os.environ` outside entrypoint, no secrets in source control

## Current state

| Asset | Status |
| :--- | :--- |
| `ARCHITECTURE.md` | Present — defines layer layout and file names |
| `ENVIRONMENT_SETUP.md` | Present — defines `uv` workflow, deps, secrets routing |
| `.gitignore` | Present — covers `.venv`, `.env`, caches |
| `pyproject.toml` / `uv.lock` | **Missing** |
| `src/mcp_server/` | **Missing** |
| `.env.example` | **Missing** |
| `changelog/` | **Missing** (this file is the first entry) |
| `uv` | Not installed at session start; Python 3.12.3 available |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `pyproject.toml` or lockfile | entrypoint | P0 |
| No virtual environment / deps installed | entrypoint | P0 |
| No `src/mcp_server/` tree | all | P0 |
| No `Settings` / `bootstrap_environment()` | entrypoint | P0 |
| No `.env.example` template | entrypoint | P1 |
| No ruff/mypy/pytest config | dev | P1 |
| No smoke test | dev | P2 |

## Minimal increment

Bootstrap the full project skeleton: `uv`-managed environment with locked dependencies, every file named in `ARCHITECTURE.md` as a minimal stub (ports, placeholders, entrypoint wiring), plus `.env.example` and a single smoke test that imports the package. Defer real MCP tools, LangChain agents, and infrastructure implementations.

### Scope (in)

- `uv init` workflow: `pyproject.toml`, `uv.lock`, `.venv`
- All architecture files as importable stubs with correct layer boundaries
- `main.py` with `bootstrap_environment()`, `Settings`, and `main()` stub
- `.env.example`, ruff/mypy/pytest tool config
- One smoke test: `import mcp_server`

### Scope (out / deferred)

- Real MCP tool implementations
- LangChain agent/graph logic
- Supabase, DuckDuckGo, YouTube adapter implementations
- CI workflow YAML
- Integration tests against external APIs

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `pyproject.toml` | create | Project metadata, deps, tool config per ENVIRONMENT_SETUP |
| `uv.lock` | create | Reproducible installs |
| `.env.example` | create | Committed secrets template |
| `src/mcp_server/**` | create | Architecture file tree |
| `tests/test_smoke.py` | create | Verify package imports |
| `changelog/2026-07-21/entrypoint/IMPLEMENTATION1.md` | create | Execution checklist |

## Dependencies & environment

- Runtime deps: fastmcp, langchain, langgraph, pydantic>=2, supabase, duckduckgo-search, google-api-python-client, python-dotenv, pydantic-settings
- Dev deps: pytest, pytest-asyncio, ruff, mypy, httpx
- Secrets / env vars: APP_ENV, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, YOUTUBE_API_KEY (optional), LOG_LEVEL
- Commands: `uv python install 3.12`, `uv sync --all-groups`, `uv run pytest`

## Risks & open questions

- `Settings` requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` at validation time — smoke test must not instantiate Settings without env vars, or test must set dummy values
- Pinning `fastmcp` to exact version after initial resolve per ENVIRONMENT_SETUP best practice

## Handoff to implementation

IMPLEMENTATION1.md should order: pyproject → uv lock/sync → scaffold all layers → .env.example → smoke test → ruff/mypy/pytest gates.
