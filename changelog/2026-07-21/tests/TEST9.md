# Test Inventory 9: Port-call timing spans + per-tool latency (BL-017, BL-019)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [infrastructure/INVESTIGATION3.md](../infrastructure/INVESTIGATION3.md), [infrastructure/IMPLEMENTATION3.md](../infrastructure/IMPLEMENTATION3.md), [infrastructure/CODE_REVIEW3.md](../infrastructure/CODE_REVIEW3.md)

## Scope

Homologate infrastructure increment 3 — Batch 3 observability:

- **BL-017** — `port_observability.py` async `port_call_span` logs INFO structured spans (`operation`, `duration_ms`, `cache` ∈ hit|miss|disabled) around `CachedDataRepository.find_documents`, `CachedSearchClient.search`, and `CachedVideoSearchClient.search_videos`; DEBUG cache hit/miss via `record_cache_hit`/`record_cache_miss` unchanged
- **BL-019** — `_cached_tool_invoke` in `custom_tools.py` logs INFO per-tool latency (`tool`, `duration_ms`, `outcome` ∈ success|error) without importing infrastructure

Layers touched: infrastructure (`port_observability.py`, `cached_adapters.py`), interface (`custom_tools.py`). Prior inventories TEST1–TEST8 remain valid.

## Test catalog

### port_observability — cache-disabled pass-through (BL-017)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C25 | `test_c25_port_call_span_logs_disabled_on_cache_bypass` | `PortCallSpan.cache` default `"disabled"`; `log_port_call` INFO format | `CachedDataRepository` with `SUPABASE_FIND_DOCUMENTS` rule `enabled=False`; caplog at INFO on `port_observability` logger | Single span: `operation=supabase.find_documents`, `cache=disabled`, `duration_ms=` present | Assert log substrings from `operation.value`; no hard-coded duration |

### port_observability — cache miss then hit (BL-017)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C26 | `test_c26_port_call_span_logs_miss_then_hit` | `cached_adapters.find_documents` sets `span.cache` on hit/miss | `CachedDataRepository` with enabled rule; two identical `find_documents` calls | Two spans; first `cache=miss`, second `cache=hit` | Count operation log lines; assert both cache statuses in caplog |
| C27 | `test_c27_port_call_span_logs_miss_then_hit_for_web_search` | `cached_adapters.search` uses `web.search` operation | `CachedSearchClient` with enabled `WEB_SEARCH` rule; two identical `search` calls | Two spans; `operation=web.search`; miss then hit | Same caplog pattern as C26; operation from `CacheOperationType.WEB_SEARCH.value` |
| C28 | `test_c28_port_call_span_logs_miss_then_hit_for_youtube_search_videos` | `cached_adapters.search_videos` uses `youtube.search_videos` operation | `CachedVideoSearchClient` with enabled `YOUTUBE_SEARCH_VIDEOS` rule; two identical `search_videos` calls | Two spans; `operation=youtube.search_videos`; miss then hit | Same caplog pattern as C26; operation from `CacheOperationType.YOUTUBE_SEARCH_VIDEOS.value` |

### custom_tools — per-tool latency (BL-019)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T27 | `test_t27_health_check_logs_tool_timing` | `_cached_tool_invoke` success branch logs INFO | Call public `health_check()` tool; caplog at INFO on `custom_tools` logger | Log contains `tool=health_check`, `duration_ms=`, `outcome=success` | Black-box tool call; assert log fields from contract string format |
| T28 | `test_t28_cached_tool_invoke_logs_error_outcome` | `_cached_tool_invoke` except branch logs `outcome=error` before re-raise | Direct `_cached_tool_invoke` with failing invoker; caplog at INFO | Log contains `tool=health_check`, `duration_ms=`, `outcome=error`; no `outcome=success` | `pytest.raises` on original exception; assert error outcome only |

## Deferred (not testable yet)

- **`trace_id` correlation (BL-020)** — explicitly out of scope per INVESTIGATION3
- **Port spans on raw adapters when `CACHE_ENABLED=false`** — wiring returns unwrapped `SupabaseRepository` / clients; spans only inside `Cached*` wrappers
- **`cached_llm.py` port timing** — not in BL-017 port list
- **LOG_LEVEL gating of port/tool spans** — `configure_logging` covered in TEST8; spans always emit at INFO when logger level permits
- **`port_call_span` duration on delegate exception** — `finally` logs duration (implementation detail); no dedicated error-path port-span test
- **`BACKLOG.md` updates** — procedural; master handles post-homologation

## Handoff to implementation

[IMPLEMENTATION9.md](./IMPLEMENTATION9.md)
