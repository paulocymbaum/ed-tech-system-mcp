# Code Review 3: Composition root cache wiring and observability

**Date:** 2026-07-21
**Layer:** entrypoint
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION3.md](./INVESTIGATION3.md)
- [IMPLEMENTATION3.md](./IMPLEMENTATION3.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `4b2835d` | include redis cache logic *(cache foundation — pre-increment)* |
| `c5b5a60` | Enhance LLM integration and operational configuration |
| `eef9003` | Refactor caching logic and enhance workflow integration *(operational config / partial wiring)* |

**Uncommitted (working tree at review time):** Increment 3 deliverables — `ApplicationContext`, runtime accessors, `custom_tools` cache wrapper, `McpToolCacheEnvelope`, `cache_observability`, production-cache docs, and associated tests — are **not yet committed**. No SHA exists for this increment.

## Summary

INVESTIGATION3 and IMPLEMENTATION3 are implemented on the working tree: a single shared `ICacheStore` in `ApplicationContext`, workflow and MCP tool cache wired through `initialize_application_runtime()`, application-layer runtime accessors consumed by `custom_tools.py`, typed MCP tool cache envelope, hit/miss observability, and production cache documentation in `ENVIRONMENT_SETUP.md`. Layer boundaries are respected — the interface imports the application port (`McpToolCachePort`), not infrastructure. All quality gates pass locally (86 tests). **Verdict is request changes** — code quality is merge-ready, but increment 3 must be committed before merge; several checklist items reference `.env.example`, which is gitignored and cannot ship via git.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION3 | All scope (in) items delivered on disk. Scope (out) correctly deferred (BL-001 orchestration, BL-015/016 stampede/compression, BL-022 HTTP adapters, `build_search_client` wiring). Status `done` matches working tree. |
| IMPLEMENTATION3 | All 20 checklist items checked; status `done` matches code on disk. Quality gates re-confirmed in this review. Item 9 (`.env.example`) is done locally but conflicts with `*.env.*` gitignore — see Warnings. |
| ARCHITECTURE.md | Patterns followed: composition root in `wiring.py`, Pydantic envelope at infrastructure boundary, interface depends on application ports. **Drift:** file tree omits `ApplicationContext`, `workflow_runtime.py`, `mcp_tool_cache_runtime.py`, `cache_envelope.py`, `cache_observability.py`. |
| ENVIRONMENT_SETUP.md | Production cache requirement section added (BL-012): `CACHE_ENABLED=true`, `REDIS_URL`, Doppler deployment checklist, graceful degradation note. Aligns with investigation. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `ApplicationContext` + shared cache in `wiring.py` | `ApplicationContext` dataclass; `create_cache_store` called once in `initialize_application_runtime` | match *(uncommitted)* |
| Runtime accessors (`workflow_runtime`, `mcp_tool_cache_runtime`) | Both modules created with set/get/reset helpers | match *(uncommitted, new files)* |
| Wire workflow + MCP tool cache at startup | `initialize_application_runtime` builds and sets both accessors | match *(uncommitted)* |
| `custom_tools.py` async `health_check` with `get_or_invoke` | Implemented via `get_mcp_tool_cache()` application port | match *(uncommitted)* |
| `McpToolCacheEnvelope` + wire in `mcp_tool_cache.py` | No `json.dumps(default=str)` or `# type: ignore` on deserialize | match *(uncommitted)* |
| `cache_observability.py` + hooks in adapters/LLM | Debug logging + in-process counters | match *(uncommitted)* |
| Test: single `create_cache_store` per boot | `test_c21_initialize_application_runtime_creates_single_cache_store` | match *(uncommitted)* |
| Test: tool cache integration | `test_t21_health_check_uses_tool_cache_on_second_identical_call` | match *(uncommitted)* |
| Test: envelope round-trip | `test_c22_mcp_tool_cache_envelope_round_trips_complex_result` | match *(uncommitted)* |
| Test: hit log on second call | `test_c23_cached_repository_logs_hit_on_second_call` | match *(uncommitted)* |
| `ENVIRONMENT_SETUP.md` production cache section | Added | match *(uncommitted)* |
| `.env.example` deployment checklist | Updated locally with cache comments | partial — file gitignored, not in index |
| `BACKLOG.md` BL-002/003/008/012/018 done | Marked done with `done-2026-07-21` tag | match *(uncommitted)* |
| Deferred: `build_search_client` wiring | Annotated in `build_search_client` docstring | match |
| Deferred: BL-001 orchestration | `get_document_video_workflow()` wired but no MCP tool consumes it yet | match (deferred) |

## Layer review (entrypoint)

### Files reviewed

- `src/mcp_server/wiring.py` — `ApplicationContext`; single `create_cache_store` in `initialize_application_runtime`; shared cache passed to `build_chat_model`, `build_document_video_workflow`, `build_mcp_tool_cache`; deferred `build_search_client` annotation
- `src/mcp_server/main.py` — unchanged bootstrap order; calls `initialize_application_runtime(operational_config, _settings)` (settings path wires cache)
- `src/mcp_server/application/workflow_runtime.py` — workflow accessor (new)
- `src/mcp_server/application/mcp_tool_cache_runtime.py` — `McpToolCachePort` protocol + accessor (new)
- `src/mcp_server/interface/custom_tools.py` — async `health_check` via application port
- `src/mcp_server/infrastructure/cache_envelope.py` — `McpToolCacheEnvelope` (new; cross-layer support for BL-008)
- `src/mcp_server/infrastructure/cache_observability.py` — hit/miss logging + counters (new; cross-layer support for BL-018)
- `src/mcp_server/infrastructure/mcp_tool_cache.py` — typed envelope serialization
- `src/mcp_server/infrastructure/cached_adapters.py`, `cached_llm.py` — observability hooks
- `tests/test_cache.py`, `tests/test_interface_tools.py`, `tests/test_entrypoint.py` — wiring and integration coverage
- `ENVIRONMENT_SETUP.md`, `backlog/BACKLOG.md` — production cache docs and backlog closure

### Architecture & patterns

- Single composition root: `initialize_application_runtime` creates one `ICacheStore` and passes it to all cache-aware builders.
- Interface layer uses `get_mcp_tool_cache()` from application (`McpToolCachePort` protocol) — no direct infrastructure import in `custom_tools.py`.
- `main.py` remains the sole `load_dotenv()` site; `Settings` validated before runtime init.
- `ApplicationContext` returned from `initialize_application_runtime` but discarded in `main()` — acceptable for this increment; enables future shutdown hooks.
- Builders retain `cache if cache is not None else create_cache_store(settings)` fallback for standalone/test calls — composition-root path is correct; fallback is a regression vector if misused.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (interface → application port, not infrastructure)
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **Increment 3 is uncommitted.** At review time, git status shows 6 new untracked files (`workflow_runtime.py`, `mcp_tool_cache_runtime.py`, `cache_envelope.py`, `cache_observability.py`, `INVESTIGATION3.md`, `IMPLEMENTATION3.md`) and 11 modified files with unstaged increment-3 changes. Merging `testbranch` as-is would **not** ship BL-002, BL-003, BL-008, BL-012, or BL-018. Commit the full increment before merge.

### Warnings (should fix)

- **`.env.example` cannot be version-controlled (BL-012 partial).** IMPLEMENTATION3 item 9 marks `.env.example` updated, and `ENVIRONMENT_SETUP.md` step 4 references mirroring keys there — but `.env.example` matches `.gitignore` rule `*.env.*` and is not tracked (`git ls-files .env.example` empty). Production checklist is committed only in `ENVIRONMENT_SETUP.md`. Update IMPLEMENTATION3 / ENVIRONMENT_SETUP to stop claiming a committed `.env.example` artifact, or route cache var templates through Doppler bootstrap scripts instead.
- **Builder fallback can bypass single-store guarantee.** `build_chat_model`, `build_document_video_workflow`, and `build_mcp_tool_cache` each call `create_cache_store(settings)` when `cache=None`. Direct calls outside `initialize_application_runtime` can recreate stores. Consider requiring `cache` when `settings.cache_enabled` or documenting builders as composition-root-only.
- **`get_document_video_workflow()` has no MCP consumer yet.** Wired at startup per BL-002, but no interface tool calls it — intentional deferral to BL-001; ensure BL-001 picks up the accessor.
- **`ARCHITECTURE.md` file tree drift.** New composition-root and runtime accessor modules are not listed in the canonical layout.

### Suggestions (consider)

- Capture `ApplicationContext` in `main()` for future cache-store lifecycle (`close()` on shutdown).
- Extend `test_e01_main_startup_loads_operational_config_before_mcp_server` to assert `initialize_application_runtime` receives settings (not only operational config) so the cache wiring path is locked.
- Add observability test for `cached_llm.py` hit path (repository hit is covered in `test_c23`; LLM path is not).

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (40 source files) |
| `uv run pytest` | pass (86 tests) |

## Verdict

**request changes**

Implementation on the working tree matches INVESTIGATION3 and IMPLEMENTATION3, respects Clean Architecture layer rules, passes all CI-equivalent gates, and closes the five backlog items in scope. **Commit the full increment** (source, tests, changelog, docs) before merge. Resolve the `.env.example` / gitignore policy tension for BL-012 documentation traceability.
