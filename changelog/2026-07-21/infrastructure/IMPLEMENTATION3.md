# Implementation 3: Port-call timing spans + per-tool latency (BL-017, BL-019)

**Date:** 2026-07-21
**Layer:** infrastructure (primary); interface (tool timing)
**Investigation:** [INVESTIGATION3.md](./INVESTIGATION3.md)
**Status:** done

## Summary

Added `port_observability.py` with async `port_call_span` context manager logging INFO structured spans (`operation`, `duration_ms`, `cache` ∈ hit|miss|disabled). Wrapped all three cached adapter port methods including cache-disabled pass-through. Extended `_cached_tool_invoke` in `custom_tools.py` with INFO tool latency logs (`tool`, `duration_ms`, `outcome`). Tests C25/C26 (port spans) and T27 (tool timing) added.

## Checklist

- [x] **1.** Create `src/mcp_server/infrastructure/port_observability.py`
- [x] **2.** Instrument `cached_adapters.py` — `find_documents`, `search`, `search_videos`
- [x] **3.** Add tool timing to `_cached_tool_invoke` in `custom_tools.py`
- [x] **4.** Add port span tests in `tests/test_cache.py` (disabled, miss, hit paths)
- [x] **5.** Add tool timing test in `tests/test_interface_tools.py`
- [x] **6.** Run `uv run ruff check src/` and fix issues
- [x] **7.** Run `uv run mypy src/`
- [x] **8.** Run `uv run pytest`
- [x] **9.** Update investigation status; set implementation status to `done`

## Task details

### 1. `port_observability.py`

- **File(s):** `src/mcp_server/infrastructure/port_observability.py`
- **Done when:** `PortCallSpan` dataclass, `port_call_span` async context manager, `log_port_call` at INFO with `operation`, `duration_ms`, `cache`

### 2. `cached_adapters.py`

- **Done when:** Each port method uses `async with port_call_span(...)`; sets `span.cache` to hit/miss/disabled; existing `record_cache_hit`/`record_cache_miss` unchanged

### 3. `custom_tools.py`

- **Done when:** `_cached_tool_invoke` logs INFO `mcp tool tool=... duration_ms=... outcome=success|error` around cache + invoker path

### 4–5. Tests

- **Done when:** `caplog` at INFO on `port_observability` logger asserts span fields; tool test asserts timing log for `health_check`

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules
- [x] BL-017 and BL-019 acceptance criteria met

## Verification results

```
uv run ruff check src/  → All checks passed
uv run mypy src/        → Success: no issues found in 40 source files
uv run pytest           → 113 passed (post-remediation; was 110)
```

## Deviations

None. Wiring unchanged: raw adapters when `CACHE_ENABLED=false` still have no port spans (documented in investigation scope out).

## Remediation (Stage 3)

**Source:** [CODE_REVIEW3.md](./CODE_REVIEW3.md) — approve with nits (warnings 1–2)

### Checklist

- [x] **R1.** Add `test_c27_port_call_span_logs_miss_then_hit_for_web_search` in `tests/test_cache.py`
- [x] **R2.** Add `test_c28_port_call_span_logs_miss_then_hit_for_youtube_search_videos` in `tests/test_cache.py`
- [x] **R3.** Add `test_t28_cached_tool_invoke_logs_error_outcome` in `tests/test_interface_tools.py` (caplog at INFO on interface logger)
- [x] **R4.** Run `uv run ruff check src/`
- [x] **R5.** Run `uv run mypy src/`
- [x] **R6.** Run `uv run pytest`

### Deferred (not in scope)

- Uncommitted delivery — procedural; master handles commits.

### Verification results (remediation)

```
uv run ruff check src/  → All checks passed
uv run mypy src/        → Success: no issues found in 40 source files
uv run pytest           → 113 passed
```
