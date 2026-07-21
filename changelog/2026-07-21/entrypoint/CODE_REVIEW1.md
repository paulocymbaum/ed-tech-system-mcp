# Code Review 1: Environment bootstrap and architecture scaffold

**Date:** 2026-07-21
**Layer:** entrypoint
**Branch:** testbranch
**Base:** none (no `main` or `master` branch; single root commit)
**Status:** final

## Changelog referencesb

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `d36cd88` | Add gitignore and Husky secret-safety hooks. |

## Summary

The scaffold on disk matches INVESTIGATION1 and IMPLEMENTATION1: full `src/mcp_server/` tree, `pyproject.toml`, `uv.lock`, `.env.example`, smoke tests, and all quality gates pass locally. Architecture layer boundaries are respected across domain, application, interface, infrastructure, and entrypoint. **However, the implementation itself is not committed to git** — only the hooks/docs commit exists on `testbranch`, with `pyproject.toml`, `src/`, `tests/`, `uv.lock`, and `changelog/` still untracked. Merge is blocked until the scaffold is committed.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | Scope (in) delivered on disk; scope (out) items correctly deferred (real adapters, CI, integration tests). Status `approved`. |
| IMPLEMENTATION1 | All 16 checklist items marked done; verification results recorded. Status `done`. Matches code on disk but not git history. |
| ARCHITECTURE.md | File tree matches documented layout. Ports in `domain/interfaces.py`, adapters in `infrastructure/`, Pydantic validation in `interface/validation.py`, bootstrap in `main.py`. |
| ENVIRONMENT_SETUP.md | `uv sync --frozen`, ruff, mypy, pytest all pass. `fastmcp` pinned to `3.4.4`. Dev dependency group present. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `pyproject.toml` + `uv.lock` | Present on disk; **untracked** | partial |
| `src/mcp_server/**` scaffold | 18 source files; **untracked** | partial |
| `.env.example` | Tracked in `d36cd88` | match |
| `tests/test_smoke.py` | Present on disk; **untracked** | partial |
| `main.py` bootstrap + Settings | Implemented; **untracked** | partial |
| Deferred: real MCP tools, adapters, CI | Stubs / `NotImplementedError` as planned | match |
| `changelog/` entries | Present on disk; **untracked** | partial |

## Layer review (entrypoint)

### Files reviewed

- `src/mcp_server/main.py` — sole `load_dotenv()` site; `Settings` via pydantic-settings; `main()` validates settings then starts FastMCP
- `pyproject.toml` — src layout, pinned `fastmcp==3.4.4`, ruff/mypy/pytest config
- `.env.example` — committed template with empty secret placeholders
- `tests/test_smoke.py` — imports package and layers without requiring real secrets

### Cross-layer files (scaffold scope)

- `src/mcp_server/domain/` — pure ports, schemas, exceptions; no forbidden imports
- `src/mcp_server/application/workflows.py` — depends on `IDataRepository` / `IVideoSearchClient` ports only
- `src/mcp_server/interface/` — FastMCP instance, Pydantic I/O schemas, `health_check` stub tool
- `src/mcp_server/infrastructure/` — adapter stubs with constructor injection; methods raise `NotImplementedError`

### Architecture & patterns

- Single `load_dotenv()` in `bootstrap_environment()`; gated on `APP_ENV=development`
- `Settings` uses `SecretStr` for credentials; validated at startup via `load_settings()`
- Infrastructure adapters accept credentials via `__init__`, not env reads
- `DocumentVideoWorkflow` orchestrates via ports — no leaky MCP or Supabase coupling
- Domain uses Pydantic `BaseModel` for entities (acceptable per ARCHITECTURE.md)

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O (stubs only; `health_check` is zero-arg)
- [x] Port/adapter boundaries respected
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **Scaffold not committed.** `git status` shows `pyproject.toml`, `src/`, `tests/`, `uv.lock`, and `changelog/` as untracked. The only commit (`d36cd88`) contains hooks and docs, not the implementation IMPLEMENTATION1 claims is done. Commit the scaffold before merge.

### Warnings (should fix)

- **No base branch.** Repository has only `testbranch` with no `main`/`master`. Create a default branch and establish a merge base for future reviews.
- **`load_settings()` result unused in `main()`.** `_settings = load_settings()` validates env vars but the instance is discarded. Wire settings into adapter construction when implementations land, or prefix with `_` explicitly to signal intentional discard.
- **Hook script modifications uncommitted.** `scripts/hooks/block-env-files.sh` and `scan-secrets.sh` show unstaged changes not covered by changelog scope.

### Suggestions (consider)

- Add a `test_load_settings_requires_env` test with `monkeypatch` dummy values to exercise `Settings` validation explicitly (currently only `bootstrap_environment` is tested).
- Register additional tools via `create_mcp_server()` once workflows exist, keeping `custom_tools` as the registration site.
- When CI is in scope, add a workflow running the same gates recorded in IMPLEMENTATION1 verification.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/ tests/` | pass |
| `uv run ruff format --check src/ tests/` | pass |
| `uv run mypy src/` | pass (18 source files) |
| `uv run pytest` | pass (3 tests) |

## Verdict

**request changes**

Code quality and architecture alignment are solid for a bootstrap increment, and all local verification passes. The branch cannot be approved for merge because the implementation exists only on disk — it must be committed to git so the branch history reflects what IMPLEMENTATION1 documents as complete.
