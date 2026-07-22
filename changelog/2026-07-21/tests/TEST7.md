# Test Inventory 7: Infrastructure trivial cleanup (BL-026, BL-025, BL-024)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [infrastructure/INVESTIGATION2.md](../infrastructure/INVESTIGATION2.md), [infrastructure/IMPLEMENTATION2.md](../infrastructure/IMPLEMENTATION2.md), [infrastructure/CODE_REVIEW2.md](../infrastructure/CODE_REVIEW2.md)

## Scope

Homologate infrastructure increment 2 — three backlog cleanup items with minimal runtime behavior change:

- **BL-026** — Remove empty `TYPE_CHECKING` block from `cache_config.py` (dead-code removal; `build_cache_rule_set` unchanged)
- **BL-025** — Delete unused `external_apis.py` placeholder; update architecture doc file trees
- **BL-024** — Document async-only `CachedChatModel` cache contract (`_agenerate` caches; `_generate` bypasses)

Primary deliverable is documentation and deletion. Existing cache and LLM tests from prior inventories (TEST1–TEST6) cover most observable contracts.

## Test catalog

### cache_config — happy path (BL-026)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| INF26 | `test_c09_build_cache_rule_set_applies_ttl_override` | `build_cache_rule_set` + `CacheSettings` protocol | Settings with `CACHE_TTL_SUPABASE_FIND_DOCUMENTS=42` | Rule for `SUPABASE_FIND_DOCUMENTS` has `enabled=True`, `ttl_seconds=42` | Assert `rules.for_operation(...).ttl_seconds` from settings env, not hard-coded stub |

### external_apis — deletion (BL-025)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| INF25 | — (no test) | INVESTIGATION2: zero importers | N/A | Module removed; no runtime entrypoint | Deletion verified by investigation `rg`; no callable contract to assert |

### CachedChatModel — async cache path (BL-024)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| INF24a | `test_llm04_cached_chat_model_hits_cache_on_second_ainvoke` | `CachedChatModel` class docstring: `_agenerate` caches | `CachedChatModel` + `InMemoryCacheStore` + enabled LLM rule | Second `ainvoke` returns same content; inner called once; cache get/set counts | Assert `StubChatModel.calls == 1`, `cache.set_calls == 1` |
| INF24c | `test_c24_cached_llm_logs_hit_on_second_call` | `cached_llm.py` observability on cache hit | Same async setup via `_agenerate` | Cache metrics: 1 hit, 1 miss; debug log contains "cache hit" | Assert `get_cache_metrics()` and caplog |

### CachedChatModel — sync bypass (BL-024)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| INF24b | `test_llm04b_cached_chat_model_sync_generate_bypasses_cache` | `CachedChatModel` docstring: `_generate` bypasses cache | `CachedChatModel` + enabled LLM rule; call `_generate` twice | Inner model invoked twice; cache store never read or written | Assert `StubChatModel.calls == 2`, `cache.get_calls == 0`, `cache.set_calls == 0` |

### CachedChatModel — wiring (BL-024 context)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| INF24d | `test_llm07_build_chat_model_wraps_with_cache_when_enabled` | `wiring.build_chat_model` | `CACHE_ENABLED=true` + cache store | Returns `CachedChatModel` wrapper | Assert `type(model).__name__` |

## Deferred (not testable yet)

- **BL-024 sync cache path** — `_generate` caching deferred until sync LLM callers exist in production (per INVESTIGATION2)
- **BL-025 module absence** — file deletion has no runtime API; import absence is not a caller-visible contract
- **BL-026 TYPE_CHECKING removal** — lint/dead-code cleanup with no behavioral delta beyond INF26 regression guard
- **ARCHITECTURE.md / AGENTIC_ARCHITECTURE.md** — documentation-only; not unit-testable

## Handoff to implementation

[IMPLEMENTATION7.md](./IMPLEMENTATION7.md)
