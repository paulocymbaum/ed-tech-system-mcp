# Test Inventory 2: Redis cache layer contracts

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [infrastructure/INVESTIGATION1.md](../infrastructure/INVESTIGATION1.md), [infrastructure/IMPLEMENTATION1.md](../infrastructure/IMPLEMENTATION1.md), [infrastructure/CODE_REVIEW1.md](../infrastructure/CODE_REVIEW1.md)

## Scope

Validate the Redis cache increment across domain, infrastructure, entrypoint wiring:

- Domain cache port (`ICacheStore`), rules (`CacheRule`/`CacheRuleSet`), deterministic `build_cache_key()`
- Infrastructure cache-aside wrappers (`CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient`)
- MCP tool interaction cache (`McpToolInteractionCache`)
- Redis adapter graceful degradation (`RedisCacheStore`, `NoOpCacheStore`)
- Settings → rules mapping (`build_cache_rule_set`) and composition root (`wiring.py`)

Existing coverage: `tests/test_cache.py` (10 tests). This inventory adds catalog IDs for those cases plus gaps noted in CODE_REVIEW1.

## Test catalog

### Domain — `build_cache_key` and `CacheRuleSet`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C01 | `test_c01_build_cache_key_is_deterministic` | `build_cache_key` docstring | Same operation, params, prefix twice | Identical key strings | Assert equality; prefix appears in key |
| C02 | `test_c02_build_cache_key_normalizes_dict_key_order` | `_canonicalize` sorts dict keys | Same params, different key order | Identical keys | Assert equality only |
| C12 | `test_c12_cache_rule_set_is_enabled` | `CacheRuleSet.is_enabled()` | Rule present+enabled vs missing/disabled | True only when rule exists and enabled | Construct rules from model fields; assert bool |

### Infrastructure — `CachedDataRepository`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C03 | `test_c03_cached_repository_hits_cache_on_second_call` | cache-aside pattern | Counting inner repo + in-memory `ICacheStore` | Second call returns same docs; inner called once; cache set once | Assert inner.call count and cache get/set counts |
| C04 | `test_c04_cached_repository_bypasses_cache_when_rule_disabled` | `rule.enabled` guard | `enabled=False` rule | Inner called every time; no cache writes | Assert inner.calls == 2, cache.set_calls == 0 |

### Infrastructure — `CachedVideoSearchClient`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C05 | `test_c05_cached_video_client_respects_language_and_safe_search` | key params include language, safe_search | Same query with language/safe_search variants cached | Inner called once for identical params | Assert inner.calls == 1 |

### Infrastructure — `CachedSearchClient`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C13 | `test_c13_cached_search_client_hits_cache_on_second_call` | `CachedSearchClient.search` cache-aside | Counting `ISearchClient` fake + enabled WEB_SEARCH rule | Second identical search hits cache; inner called once | Assert snippets equal and inner.calls == 1 |
| C14 | `test_c14_cached_search_client_misses_on_different_max_results` | key includes `max_results` | Same query, different max_results | Inner called for each distinct param set | Assert inner.calls == 2 |

### Infrastructure — `McpToolInteractionCache`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C15 | `test_c15_mcp_tool_cache_returns_cached_result_without_reinvoking` | `get_or_invoke` cache hit path | Async invoker counter; MCP_TOOL rule enabled | Second call returns same result; invoker called once | Assert return value and invoker count |
| C16 | `test_c16_mcp_tool_cache_bypasses_when_rule_disabled` | disabled rule guard | `enabled=False` for MCP_TOOL | Invoker called on every `get_or_invoke` | Assert invoker count == 2 |

### Infrastructure — `NoOpCacheStore` and `RedisCacheStore`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C17 | `test_c17_noop_cache_store_always_misses` | `NoOpCacheStore.get/set` | set then get arbitrary key | get returns None; set does not raise | Assert None; no exception |
| C18 | `test_c18_redis_cache_store_degrades_on_unreachable_host` | `RedisCacheStore` connect/GET failure → miss | Store with unreachable redis URL | `get` returns None without raising | `pytest.raises` must not trigger; assert None |

### Entrypoint — Settings and wiring

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C06 | `test_c06_settings_loads_redis_and_cache_fields` | `Settings` Field aliases | monkeypatch CACHE/REDIS env vars | Fields match env | Assert public settings attributes |
| C07 | `test_c07_resolve_redis_url_from_host_and_password` | `resolve_redis_url` | REDIS_HOST/PORT/PASSWORD without REDIS_URL | URL contains host, port, password auth segment | Assert resolved string format |
| C08 | `test_c08_create_cache_store_returns_none_when_disabled` | `create_cache_store` when `cache_enabled=False` | monkeypatch CACHE_ENABLED=false | Returns None | Assert identity is None |
| C09 | `test_c09_build_cache_rule_set_applies_ttl_override` | `build_cache_rule_set` TTL mapping | CACHE_TTL_SUPABASE_FIND_DOCUMENTS=42 | Rule ttl_seconds == 42, enabled follows cache_enabled | Read from settings env |
| C10 | `test_c10_build_document_video_workflow_returns_workflow` | `build_document_video_workflow` | Valid settings, cache disabled | Non-None `DocumentVideoWorkflow` | Assert workflow type |
| C11 | `test_c11_build_data_repository_without_cache_is_uncached` | `build_data_repository(..., cache=None)` | cache=None | Returns bare `SupabaseRepository` | Assert `type().__name__` |
| C19 | `test_c19_build_mcp_tool_cache_returns_none_when_disabled` | `build_mcp_tool_cache` | CACHE_ENABLED=false | Returns None | Assert None |

## Deferred (not testable yet)

- Redis cluster/sentinel production topology
- Single-flight / stampede protection
- Cache invalidation webhooks / pub-sub
- MCP tool decorator wiring in interface layer (helper exists; tools are stubs)
- `main()` invoking `build_document_video_workflow()` at startup
- Real Supabase/YouTube/DuckDuckGo adapter behavior behind cache wrappers
- Per-operation enable/disable independent of global `cache_enabled`

## Handoff to implementation

See [IMPLEMENTATION2.md](./IMPLEMENTATION2.md) for ordered test tasks and verification gates.
