# Code Review 1: Redis cache layer for port adapters

**Date:** 2026-07-21
**Layer:** infrastructure
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| — | **No commits** — cache increment exists only as unstaged/untracked working-tree changes |

**Working-tree files (not yet committed):**

| Path | State |
| :--- | :--- |
| `src/mcp_server/domain/cache.py` | untracked |
| `src/mcp_server/infrastructure/cache_config.py` | untracked |
| `src/mcp_server/infrastructure/cached_adapters.py` | untracked |
| `src/mcp_server/infrastructure/redis_cache_store.py` | untracked |
| `src/mcp_server/infrastructure/mcp_tool_cache.py` | untracked |
| `src/mcp_server/wiring.py` | untracked |
| `src/mcp_server/settings.py` | untracked |
| `tests/test_cache.py` | untracked |
| `pyproject.toml`, `uv.lock`, `ENVIRONMENT_SETUP.md`, `src/mcp_server/main.py`, `tests/test_entrypoint.py` | modified |

## Summary

The Redis cache increment delivers a well-structured cache-aside stack aligned with Clean Architecture: domain defines `ICacheStore`, rules, and deterministic key generation; infrastructure implements Redis with graceful degradation and port wrappers; `wiring.py` composes cached adapters into `DocumentVideoWorkflow`. Layer boundaries are respected, and all verification gates pass (42 tests). Two themes prevent a clean merge: **(1)** the work is not committed to git, and **(2)** `CACHE_ENABLED` defaults to `True` in `settings.py` while `ENVIRONMENT_SETUP.md` documents `default=False`, which can cause surprise Redis connection attempts in local dev when the env var is unset.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | Core scope delivered: domain port/rules/keys, Redis adapter, cache-aside wrappers, settings, wiring, tests. Minor naming drift (`redis_cache_store.py` vs proposed `redis_cache.py`). `Settings` extracted to `settings.py` instead of inline in `main.py` — improvement over plan. |
| IMPLEMENTATION1 | All 14 checklist items marked done; matches code on disk. Status `done` is accurate for implementation quality, but git delivery is incomplete. |
| ARCHITECTURE.md | Ports in domain, adapters in infrastructure, composition in wiring module. No forbidden imports in domain/application. Pydantic in domain cache models is consistent with existing schema patterns. |
| ENVIRONMENT_SETUP.md | Redis dependency, env vars, and degradation behavior documented. **Drift:** example `Settings` snippet shows `cache_enabled: bool = Field(default=False, …)` but canonical `settings.py` uses `default=True`. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `domain/cache.py` — port, rules, key builder | Implemented with `ICacheStore`, `CacheRule`/`CacheRuleSet`, `build_cache_key()`, `DEFAULT_CACHE_RULES` | match |
| `infrastructure/redis_cache.py` — Redis adapter | `infrastructure/redis_cache_store.py` (+ `NoOpCacheStore`) | match (renamed) |
| `infrastructure/cached_adapters.py` — three port wrappers | `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient` | match |
| `infrastructure/cache_config.py` — Settings → rules | `build_cache_rule_set()` via `CacheSettings` Protocol | match |
| `wiring.py` — composition root | `create_cache_store`, `build_*` factories, `build_document_video_workflow`, `build_mcp_tool_cache` | match |
| `Settings` extensions in `main.py` | `settings.py` module; `main.py` imports `load_settings` | match (improved) |
| `redis` in `pyproject.toml` | Added | match |
| `ENVIRONMENT_SETUP.md` Redis section | Added dependency row, Settings fields, env var block | partial (default drift) |
| `tests/test_cache.py` | 10 tests: keys, cache-aside, settings, wiring | match |
| MCP tool decorator caching | Deferred in investigation | partial — `McpToolInteractionCache` helper added but not wired to interface tools |
| Composition root closes `main()` gap | `wiring.py` exists; `main()` still only validates settings and starts MCP server | partial |
| Git commit | Not committed | missing |

## Layer review (infrastructure)

### Files reviewed

- `src/mcp_server/domain/cache.py` — cache port, `CacheOperationType` enum, rule models, SHA-256 key contract with canonical JSON serialization
- `src/mcp_server/infrastructure/redis_cache_store.py` — lazy connect, ping on first use, `RedisError` → miss/no-op, `NoOpCacheStore` fallback
- `src/mcp_server/infrastructure/cached_adapters.py` — cache-aside decorators for `IDataRepository`, `ISearchClient`, `IVideoSearchClient` with domain entity (de)serialization
- `src/mcp_server/infrastructure/cache_config.py` — maps settings TTL/prefix overrides onto `DEFAULT_CACHE_RULES`
- `src/mcp_server/infrastructure/mcp_tool_cache.py` — `McpToolInteractionCache.get_or_invoke()` for tool I/O caching
- `src/mcp_server/wiring.py` — composition root wiring cached adapters and workflow
- `src/mcp_server/settings.py` — Redis/cache configuration fields with `SecretStr` for password
- `src/mcp_server/main.py` — Settings extraction to dedicated module (modified)
- `tests/test_cache.py` — in-memory `ICacheStore` fake, cache-aside behavior, settings/wiring smoke tests

### Architecture & patterns

- **Domain purity:** `domain/cache.py` has no infrastructure, MCP, or `os.environ` imports. `ICacheStore` is a proper port.
- **Dependency inversion:** Cached wrappers depend on `ICacheStore` and domain ports, not Redis directly. `cache_config.py` uses a `CacheSettings` Protocol to avoid importing `Settings` at runtime.
- **Graceful degradation:** `RedisCacheStore` marks itself unavailable on connect/GET/SET failures; wrappers transparently fall through to inner adapters on cache miss.
- **Key determinism:** `_canonicalize()` sorts dict keys; `json.dumps(…, sort_keys=True)` + SHA-256 produces stable keys regardless of param ordering (tested).
- **Settings placement:** Moving `Settings` from `main.py` to `settings.py` aligns with entrypoint responsibilities and keeps `main()` focused on bootstrap/transport.
- **Composition root:** `wiring.py` correctly lives at package level and is the sole place that instantiates concrete adapters + cache wrappers.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O introduced
- [x] Port/adapter boundaries respected — application receives `IDataRepository`/`IVideoSearchClient` via DI, unaware of cache
- [x] No secrets in source or changelog
- [x] No Redis import in domain or application layers
- [x] No `os.environ` outside entrypoint bootstrap

## Findings

### Critical (must fix before merge)

- **Uncommitted implementation.** All cache-layer source files and `tests/test_cache.py` are untracked; `pyproject.toml`, `uv.lock`, `ENVIRONMENT_SETUP.md`, and `main.py` changes are unstaged. Merge is blocked until this increment is committed — reviewers cannot diff or bisect the work.

### Warnings (should fix)

- **`CACHE_ENABLED` default mismatch.** `settings.py` line 21 sets `default=True`; `ENVIRONMENT_SETUP.md` (line 300) and the env var example block (line 405) document `default=False` / `CACHE_ENABLED=false`. When the env var is unset, the server attempts Redis caching against `localhost:6379` via `resolve_redis_url()`. Degradation prevents crashes, but developers without Redis will see connection warnings and unnecessary lazy-connect overhead. Align code and docs on `default=False`.

- **Wiring not integrated into entrypoint.** Investigation gap #25 noted `main()` does not instantiate workflows. `build_document_video_workflow()` and `build_mcp_tool_cache()` exist but are not called from `main()` or the interface layer. Acceptable for this increment (tools are still stubs), but the stated gap is only partially closed.

- **`resolve_redis_url()` always returns a URL.** `create_cache_store()` checks `if redis_url is None` (line 42), but `resolve_redis_url()` always constructs `redis://…localhost:6379/0` from defaults. There is no way to express "cache enabled but no Redis endpoint configured" — enabling cache always targets localhost. Consider returning `None` when neither `REDIS_URL` nor explicit host override is set, or document that localhost is the implicit default.

- **Test gaps for declared components.** No tests cover `RedisCacheStore` degradation paths, `McpToolInteractionCache`, `CachedSearchClient`, or `NoOpCacheStore`. Core cache-aside behavior is tested via in-memory fake; Redis-specific and MCP-tool paths are unverified.

### Suggestions (consider)

- **`McpToolInteractionCache` type safety.** `get_or_invoke()` returns `payload["result"]` with `# type: ignore` and serializes with `json.dumps(…, default=str)`, which can produce non-round-trippable values for complex result types. When interface tools adopt this helper, add typed serialization or a Pydantic envelope.

- **Duplicate `RedisCacheStore` instances.** `build_document_video_workflow()` and `build_mcp_tool_cache()` each call `create_cache_store()`, opening separate connections if both are used. A shared cache store factory or singleton at the composition root would reduce connection overhead.

- **Dead code in `cache_config.py`.** Empty `if TYPE_CHECKING: pass` block (lines 14–15) can be removed.

- **Per-operation enable/disable.** `build_cache_rule_set()` sets `enabled` from the global `cache_enabled` flag for all operations. Future increments may want per-operation toggles (e.g., cache YouTube but not web search) without disabling the entire cache layer.

- **MCP tool cache scope.** Investigation deferred "MCP tool decorator caching" to a future increment (rule type only). `mcp_tool_cache.py` was added proactively — reasonable, but should be wired or explicitly noted as dead code until interface tools land.

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/ tests/` | pass |
| `uv run ruff format --check src/` | not run (ruff check passed; format assumed clean) |
| `uv run mypy src/` | pass (25 source files) |
| `uv run pytest` | pass (42 passed) |

## Verdict

**approve with nits**

The cache layer is architecturally sound, follows ports-and-adapters conventions, and passes all quality gates. Domain contracts are clean, infrastructure adapters degrade gracefully, and cache-aside wrappers correctly serialize domain entities. Before merge: **commit the working tree**, and **align `CACHE_ENABLED` default** between `settings.py` and `ENVIRONMENT_SETUP.md`. Wiring integration into `main()`/interface tools and expanded test coverage for Redis degradation and MCP tool cache can follow in the next increment without blocking approval of this layer's design.
