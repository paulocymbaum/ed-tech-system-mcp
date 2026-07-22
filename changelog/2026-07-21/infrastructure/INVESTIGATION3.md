# Investigation 3: Port-call timing spans + per-tool latency (BL-017, BL-019)

**Date:** 2026-07-21
**Layer:** infrastructure (primary); interface (tool timing)
**Status:** approved

## User request

Batch 3 — observability backlog items in one increment:

- **BL-017** — Structured log spans around port calls (`find_documents`, `search_videos`, `search`) with `duration_ms`, operation name, and cache hit/miss flag; respect `LOG_LEVEL` (DEBUG for cache detail, INFO for port timing).
- **BL-019** — Per-MCP-tool latency breakdown in `custom_tools.py` via `_cached_tool_invoke`; log tool name, `duration_ms`, outcome at INFO; add test.

Constraints: no `trace_id` (BL-020 deferred); interface must not import infrastructure for timing; reuse/extend `cache_observability.py` or sibling module.

## Architecture alignment

- **Layers touched:** infrastructure (`port_observability.py`, `cached_adapters.py`), interface (`custom_tools.py` timing in `_cached_tool_invoke`)
- **Patterns applied:** Infrastructure observability helper; structured key=value logging; existing DEBUG cache hit/miss via `record_cache_hit`/`record_cache_miss` unchanged
- **Anti-patterns avoided:** No infrastructure import in interface; no trace_id; no backlog edits; no `os.environ` in observability modules

## Current state

| Asset | Status |
| :--- | :--- |
| `cache_observability.py` | DEBUG hit/miss logging + in-process counters (BL-018 done) |
| `cached_adapters.py` | Cache-aside for `find_documents`, `search`, `search_videos`; early pass-through when rule disabled; no `duration_ms` |
| `wiring.py` | When `CACHE_ENABLED=false`, returns raw adapters (no `Cached*` wrapper) — port spans only fire when cached wrapper is used |
| `custom_tools.py` | All four tools route through `_cached_tool_invoke`; no per-tool latency logging |
| `main.py` | `configure_logging(settings)` applies `LOG_LEVEL` at boot (BL-007 done) |
| `tests/test_cache.py` | C23/C24 assert cache hit DEBUG logs; no port timing tests |
| `tests/test_interface_tools.py` | T20–T26 tool contract tests; no timing wrapper test |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `duration_ms` on port calls (BL-017) | infrastructure | high |
| Pass-through path in `cached_adapters` lacks timing span | infrastructure | high |
| No per-tool latency at INFO (BL-019) | interface | high |
| No test for tool timing wrapper | tests | medium |

## Minimal increment

Add `port_observability.py` with an async context manager that logs INFO spans (`operation`, `duration_ms`, `cache` ∈ hit|miss|disabled). Wrap all three port methods in `cached_adapters.py`, including the early pass-through when cache rule is disabled. Keep existing DEBUG hit/miss in `cache_observability.py` unchanged.

Add timing to `_cached_tool_invoke` in `custom_tools.py` (interface-local, no infrastructure import): INFO log with `tool`, `duration_ms`, `outcome` (success|error) for `health_check`, `search_youtube`, `find_documents`, `run_workflow`.

Defer wiring change to always wrap adapters (would alter `test_c11` type assertion); pass-through within `cached_adapters` satisfies "cache disabled" span requirement for wrapped instances.

### Scope (in)

- `port_observability.py` — `port_call_span` context manager + `log_port_call`
- Instrument `CachedDataRepository.find_documents`, `CachedSearchClient.search`, `CachedVideoSearchClient.search_videos`
- Tool timing in `_cached_tool_invoke`
- Tests: port span on miss/hit/disabled paths; tool timing via `caplog` at INFO
- `ruff`, `mypy`, `pytest`

### Scope (out / deferred)

- `trace_id` correlation (BL-020)
- Port spans when wiring returns raw `SupabaseRepository` / `YouTubeDataApiClient` (cache globally disabled)
- `cached_llm.py` port timing (not in BL-017 port list)
- `backlog/BACKLOG.md` updates

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/infrastructure/port_observability.py` | create | Shared port-call span helper |
| `src/mcp_server/infrastructure/cached_adapters.py` | modify | Wrap port methods with timing spans |
| `src/mcp_server/interface/custom_tools.py` | modify | BL-019 timing in `_cached_tool_invoke` |
| `tests/test_cache.py` | modify | Port span tests (C25+) |
| `tests/test_interface_tools.py` | modify | Tool timing test (T27) |

## Dependencies & environment

- Runtime deps: none (stdlib `logging`, `time`)
- Dev deps: none
- Secrets / env vars: `LOG_LEVEL` (already wired)
- Commands: `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Risk:** Double logging noise at INFO — mitigated by keeping cache detail at DEBUG only.
- **Risk:** Raw adapters when `CACHE_ENABLED=false` have no spans — documented as deferred; tests use `CachedDataRepository` directly.

## Handoff to implementation

IMPLEMENTATION3.md should checklist: create `port_observability.py`, refactor three cached adapter methods, add `_cached_tool_invoke` timing, add C25/C26/C27 and T27 tests, run verification gates.
