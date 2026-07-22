# Investigation 3: Composition root cache wiring and observability

**Date:** 2026-07-21
**Layer:** entrypoint
**Status:** done

## User request

Wire composition root with shared cache store, MCP tool cache integration, production cache docs, typed cache serialization, and cache hit/miss observability — covering BL-003, BL-002, BL-012, BL-008, BL-018.

## Architecture alignment

- **Layers touched:** entrypoint (primary — `main.py`, `wiring.py`), interface (`custom_tools.py`, runtime accessors), application (workflow/MCP cache ports), infrastructure (`mcp_tool_cache.py`, `cached_adapters.py`, `cached_llm.py`, cache observability)
- **Patterns applied:** Single composition root (`ApplicationContext`), dependency injection of shared `ICacheStore`, application-layer runtime accessors (mirrors `set_chat_model`), Pydantic serialization envelope at infrastructure boundary, graceful Redis degradation (existing)
- **Anti-patterns avoided:** No duplicate `create_cache_store()` per boot, no interface→infrastructure direct import (use application port), no secrets in docs

## Current state

| Asset | Status |
| :--- | :--- |
| `wiring.py` | `create_cache_store()` called independently in `build_chat_model`, `build_document_video_workflow`, `build_mcp_tool_cache` (lines 122, 145, 153) |
| `main.py` | Calls `initialize_application_runtime()` only; does not wire workflow or MCP tool cache |
| `custom_tools.py` | Only `health_check`; no cache wrapper |
| `mcp_tool_cache.py` | Uses `json.dumps(..., default=str)` with `# type: ignore` on deserialize |
| `cached_adapters.py` / `cached_llm.py` | No hit/miss debug logging or counters |
| `ENVIRONMENT_SETUP.md` | Documents optional Redis cache; no production enablement checklist |
| `.env.example` | Minimal Redis comments; no production guidance |
| Tests | Cache contract tests exist (C01–C20); no single-store boot test, no hit-log test, no MCP tool integration via entrypoint |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Three `create_cache_store()` calls per boot | entrypoint / wiring | P0 (BL-003) |
| Workflow and MCP tool cache not wired at startup | entrypoint / interface | P0 (BL-002) |
| Production cache requirements undocumented | docs | P0 (BL-012) |
| Untyped MCP tool cache JSON envelope | infrastructure | P1 (BL-008) |
| No cache hit/miss observability | infrastructure | P1 (BL-018) |

## Minimal increment

Introduce `ApplicationContext` at the composition root that creates one `ICacheStore` and passes it to `build_chat_model`, `build_document_video_workflow`, and `build_mcp_tool_cache`. Extend `initialize_application_runtime()` to wire workflow and MCP tool cache into application runtime accessors consumed by `custom_tools.py`. Wrap `health_check` with `get_or_invoke`. Add Pydantic `McpToolCacheEnvelope` for typed MCP tool cache serialization. Add debug hit/miss logging and optional counters in cached adapters. Document production `CACHE_ENABLED=true` + Redis in `ENVIRONMENT_SETUP.md` and `.env.example`.

### Scope (in)

- `ApplicationContext` dataclass + shared cache in `wiring.py`
- Application runtime accessors for workflow and MCP tool cache port
- `custom_tools.py` async `health_check` with cache wrapper
- `McpToolCacheEnvelope` in infrastructure
- `cache_observability.py` module
- Tests: single `create_cache_store` call, tool cache integration, envelope round-trip, hit log
- `ENVIRONMENT_SETUP.md` + `.env.example` production cache section
- `BACKLOG.md` updates per BL task

### Scope (out / deferred)

- BL-001 orchestration path integration
- BL-015 compression optimization
- BL-016 stampede protection
- BL-022 real HTTP adapters
- `build_search_client()` wiring (annotate deferred)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/wiring.py` | modify | `ApplicationContext`, shared cache, wire all builders |
| `src/mcp_server/main.py` | modify | Consume `ApplicationContext` from runtime init |
| `src/mcp_server/application/workflow_runtime.py` | create | Workflow runtime accessor |
| `src/mcp_server/application/mcp_tool_cache_runtime.py` | create | MCP tool cache port + accessor |
| `src/mcp_server/interface/custom_tools.py` | modify | Wrap `health_check` with cache |
| `src/mcp_server/infrastructure/mcp_tool_cache.py` | modify | Pydantic envelope serialization |
| `src/mcp_server/infrastructure/cache_envelope.py` | create | `McpToolCacheEnvelope` |
| `src/mcp_server/infrastructure/cache_observability.py` | create | Hit/miss logging + counters |
| `src/mcp_server/infrastructure/cached_adapters.py` | modify | Observability hooks |
| `src/mcp_server/infrastructure/cached_llm.py` | modify | Observability hooks |
| `ENVIRONMENT_SETUP.md` | modify | Production cache requirements |
| `.env.example` | modify | Deployment checklist comments |
| `tests/test_cache.py` | modify | New cache/wiring tests |
| `tests/test_entrypoint.py` | modify | Updated startup order test |
| `tests/test_interface_tools.py` | modify | Tool cache integration test |
| `backlog/BACKLOG.md` | modify | Mark BL tasks done |

## Dependencies & environment

- Runtime deps: unchanged (`redis`, `pydantic`)
- Dev deps: unchanged
- Secrets / env vars: `CACHE_ENABLED`, `REDIS_URL` (no `.env` changes)
- Commands: `uv sync`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- `health_check` becomes async to use `get_or_invoke`; FastMCP supports async tools — verify in test
- Shared cache store lifetime spans process boot; no explicit `close()` until shutdown hook lands (acceptable)

## Handoff to implementation

IMPLEMENTATION3.md should checklist: wiring refactor → runtime accessors → custom_tools → envelope → observability → docs → tests → quality gates → BACKLOG updates per BL in dependency order.
