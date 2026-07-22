# Code Review 3: Port-call timing spans + per-tool latency (BL-017, BL-019)

**Date:** 2026-07-21
**Layer:** infrastructure (primary); interface (tool timing)
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION3.md](./INVESTIGATION3.md)
- [IMPLEMENTATION3.md](./IMPLEMENTATION3.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| — | **No commits** — increment 3 exists only as unstaged/untracked working-tree changes on `testbranch` |

**Working-tree files in scope (infrastructure increment 3):**

| Path | Change |
| :--- | :--- |
| `src/mcp_server/infrastructure/port_observability.py` | new (untracked) |
| `src/mcp_server/infrastructure/cached_adapters.py` | modified — `port_call_span` on all three port methods |
| `src/mcp_server/interface/custom_tools.py` | modified — `_cached_tool_invoke` INFO timing (BL-019) |
| `tests/test_cache.py` | modified — C25, C26 port-span tests |
| `tests/test_interface_tools.py` | modified — T27 tool-timing test |
| `changelog/2026-07-21/infrastructure/INVESTIGATION3.md` | new (untracked) |
| `changelog/2026-07-21/infrastructure/IMPLEMENTATION3.md` | new (untracked) |

## Summary

INVESTIGATION3 and IMPLEMENTATION3 are implemented on the working tree. `port_observability.py` provides an async `port_call_span` context manager that logs INFO structured spans (`operation`, `duration_ms`, `cache` ∈ hit|miss|disabled); all three `Cached*` adapter methods wrap their bodies with it, including cache-disabled pass-through where `span.cache` defaults to `disabled`. BL-019 adds interface-local timing in `_cached_tool_invoke` without importing infrastructure. Existing DEBUG cache hit/miss logging in `cache_observability.py` is unchanged. All quality gates pass (110 tests). Verdict is **approve with nits** — acceptance criteria are met and layer boundaries respected, but the increment is uncommitted and port-span test coverage is narrower than the investigation handoff suggested.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION3 | Scope delivered: `port_observability.py`, three instrumented port methods, tool timing in `_cached_tool_invoke`, C25/C26 + T27 tests, quality gates. Deferred items respected (no `trace_id`, no raw-adapter spans when `CACHE_ENABLED=false`, no `cached_llm.py` port timing, no backlog edits). |
| IMPLEMENTATION3 | All 9 checklist items checked; status `done` matches code on disk. Correctly documents C25/C26 (not C27). No deviations recorded. |
| ARCHITECTURE.md | File tree does not yet list `port_observability.py` or `cached_adapters.py` instrumentation — doc drift only; no layer-rule violation. |
| ENVIRONMENT_SETUP.md | `LOG_LEVEL` applied at boot via `configure_logging(settings)` (BL-007); port spans at INFO and cache detail at DEBUG align with documented logging policy. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| Create `port_observability.py` with `PortCallSpan`, `port_call_span`, `log_port_call` | `port_observability.py` — stdlib `logging`/`time` only; INFO `port call operation=… duration_ms=… cache=…` | match |
| Instrument `CachedDataRepository.find_documents` | `async with port_call_span(operation.value) as span`; sets `hit`/`miss`; pass-through keeps `disabled` | match |
| Instrument `CachedSearchClient.search` | Same pattern with `web.search` operation | match |
| Instrument `CachedVideoSearchClient.search_videos` | Same pattern with `youtube.search_videos` operation | match |
| Keep `record_cache_hit`/`record_cache_miss` at DEBUG | `cache_observability.py` unchanged; adapters still call record helpers on hit/miss | match |
| BL-019: INFO tool timing in `_cached_tool_invoke` | Logs `mcp tool tool=… duration_ms=… outcome=success\|error`; no infrastructure import | match |
| Tests C25 (disabled path), C26 (miss/hit) | `test_c25_*`, `test_c26_*` in `test_cache.py` | match |
| Test T27 (tool timing) | `test_t27_health_check_logs_tool_timing` in `test_interface_tools.py` | match |
| Investigation handoff: C25/C26/C27 | Only C25/C26 delivered | partial |
| Scope out: port spans on raw adapters when `CACHE_ENABLED=false` | `wiring.py` unchanged; raw `SupabaseRepository` etc. have no spans | match (deferred) |
| Scope out: `trace_id`, backlog edits | Not implemented | match |
| Run `ruff`, `mypy`, `pytest` | All pass (110 tests) | match |

## Layer review (infrastructure)

### Files reviewed

- `src/mcp_server/infrastructure/port_observability.py` — `PortCallSpan` dataclass, `log_port_call` at INFO, `port_call_span` async context manager using `time.perf_counter()`
- `src/mcp_server/infrastructure/cached_adapters.py` — all three port methods wrapped; `span.cache` set on hit/miss; disabled pass-through relies on default `cache="disabled"`
- `src/mcp_server/infrastructure/cache_observability.py` — verified unchanged (DEBUG hit/miss only)
- `src/mcp_server/interface/custom_tools.py` — BL-019 timing wrapper; imports application runtime only, not infrastructure

### Architecture & patterns

- `port_observability.py` uses stdlib only — no MCP, LangChain, Supabase, or `os.environ`.
- Interface layer satisfies investigation constraint: timing via local `time`/`logging`, not `port_observability` import.
- Port spans fire inside `Cached*` wrappers only; composition root behavior when cache is globally disabled remains as documented in scope out.
- Structured key=value log format is consistent with existing `cache_observability` style.
- `port_call_span` logs in `finally`, so duration is recorded even when inner delegate raises.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (interface does not import infrastructure for timing)
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **Uncommitted delivery.** At review time, `port_observability.py`, `INVESTIGATION3.md`, and `IMPLEMENTATION3.md` are untracked; `cached_adapters.py`, `custom_tools.py`, and test files are modified but unstaged. Merging `testbranch` as-is would **not** ship BL-017 or BL-019. Commit the full increment before merge.
- **Port-span test coverage is partial.** Investigation handoff referenced C25/C26/C27; implementation delivers C25/C26 only, both exercising `CachedDataRepository.find_documents`. `CachedSearchClient.search` and `CachedVideoSearchClient.search_videos` are instrumented in code but lack dedicated `caplog` tests — regression risk is low given symmetric implementation, but homologation is incomplete vs handoff.
- **T27 covers success path only.** `_cached_tool_invoke` logs `outcome=error` on exception (lines 94–101), but no test asserts the error branch; BL-019 acceptance is met for the happy path only.

### Suggestions (consider)

- Add parametrized port-span tests for `web.search` and `youtube.search_videos` (the deferred C27 intent) or document C26 as sufficient representative coverage.
- Add `test_t28_*` asserting `outcome=error` when invoker raises.
- Add `port_observability.py` to the `ARCHITECTURE.md` infrastructure file tree.
- Update `backlog/BACKLOG.md` checkboxes for BL-017/BL-019 after homologation (explicitly deferred per investigation).

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (40 source files) |
| `uv run pytest` | pass (110 passed, 1 deprecation warning) |

## Verdict

**approve with nits**

BL-017 and BL-019 acceptance criteria are met on the working tree: INFO port-call spans with `duration_ms`, operation name, and cache status on all three cached port methods; DEBUG cache detail preserved; per-tool latency logged at INFO from `_cached_tool_invoke` without violating interface→infrastructure boundaries; quality gates pass. Nits are procedural (uncommitted increment), narrower test coverage than the investigation handoff (no C27 / no error-outcome test), and minor `ARCHITECTURE.md` tree drift — none block approval of the implementation design. **Commit the full increment** before merge.
