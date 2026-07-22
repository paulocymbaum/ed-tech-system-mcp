# Investigation 1: Redis cache layer for port adapters

**Date:** 2026-07-21
**Layer:** infrastructure
**Status:** approved

## User request

Define and implement Redis as a cache layer in the MCP server to reduce repetitive calls, Supabase queries, and YouTube searches by caching the input and output of each interaction based on dynamic cache rules.

## Architecture alignment

- **Layers touched:** domain (cache port, rules, key contract), infrastructure (Redis adapter, cache-aside wrappers), application (consumes wrapped ports via DI), entrypoint (Settings, composition root)
- **Patterns applied:** Ports & Adapters (`ICacheStore`), cache-aside decorator on existing ports, deterministic key generation in domain, graceful degradation at composition root
- **Anti-patterns avoided:** No Redis import in domain/application; no bypass of port boundaries; no `os.environ` outside entrypoint; no cache logic in MCP tool decorators

## Current state

| Asset | Status |
| :--- | :--- |
| `IDataRepository`, `ISearchClient`, `IVideoSearchClient` | Defined in `domain/interfaces.py` |
| `SupabaseRepository`, `DuckDuckGoSearchClient`, `YouTubeDataApiClient` | Stub adapters raising `NotImplementedError` |
| `DocumentVideoWorkflow` | Accepts repository + video client via constructor DI |
| `Settings` in `main.py` | Supabase + YouTube keys only; no Redis/cache fields |
| Composition / DI wiring | **Missing** — `main()` does not instantiate workflows or adapters |
| Redis dependency | **Not in** `pyproject.toml` |
| Cache documentation | **Not in** `ENVIRONMENT_SETUP.md` |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `ICacheStore` port or cache rule value objects | domain | P0 |
| No deterministic cache-key contract | domain | P0 |
| No Redis adapter | infrastructure | P0 |
| No cache-aside wrappers for existing ports | infrastructure | P0 |
| No Settings fields for Redis / cache rules | entrypoint | P0 |
| No composition root to wire cached adapters | entrypoint | P0 |
| No tests for cache behavior | dev | P1 |
| `redis` not in dependencies | entrypoint | P0 |

## Minimal increment

Introduce a full cache-aside stack: domain defines `ICacheStore`, `CacheOperationType`, `CacheRule`/`CacheRuleSet`, and `build_cache_key()`; infrastructure implements `RedisCacheStore` (lazy connect, JSON payloads) and cached wrappers for the three existing ports; entrypoint extends `Settings` with optional Redis and per-operation TTL overrides, plus a `wiring.py` composition module that builds cached adapters and a `DocumentVideoWorkflow` when cache is enabled or falls back to uncached adapters when disabled/unavailable. MCP tool-level caching is limited to the `CacheOperationType.MCP_TOOL` rule definition (no interface decorator yet — tools are stubs).

### Scope (in)

- `domain/cache.py` — port, rules, key generation
- `infrastructure/redis_cache.py` — `RedisCacheStore`
- `infrastructure/cached_adapters.py` — wrappers for repository, search, video ports
- `infrastructure/cache_config.py` — build `CacheRuleSet` from `Settings`
- `wiring.py` — composition root at package level
- `Settings` extensions in `main.py`
- `redis` dependency, `ENVIRONMENT_SETUP.md` Redis section
- Unit tests with in-memory `ICacheStore` fake

### Scope (out / deferred)

- Cache invalidation webhooks / pub/sub
- Single-flight / stampede protection
- LLM/agent step caching
- Redis cluster / sentinel production docs
- Real Supabase/YouTube/DuckDuckGo implementations
- MCP tool decorator caching (rule type defined only)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/domain/cache.py` | create | Cache port, rules, key contract |
| `src/mcp_server/infrastructure/redis_cache.py` | create | Redis adapter with JSON bytes |
| `src/mcp_server/infrastructure/cached_adapters.py` | create | Cache-aside port wrappers |
| `src/mcp_server/infrastructure/cache_config.py` | create | Map Settings → CacheRuleSet |
| `src/mcp_server/wiring.py` | create | Composition root; graceful degradation |
| `src/mcp_server/main.py` | modify | Redis/cache Settings fields |
| `pyproject.toml` | modify | Add `redis` runtime dep |
| `ENVIRONMENT_SETUP.md` | modify | Document Redis env vars |
| `tests/test_cache.py` | create | Key gen, cache-aside, settings, wiring |
| `changelog/.../IMPLEMENTATION1.md` | create | Execution checklist |

## Dependencies & environment

- Runtime deps: `redis` (asyncio client)
- Dev deps: unchanged (in-memory fake for tests)
- Secrets / env vars: `CACHE_ENABLED`, `REDIS_URL` or `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD`, per-rule `CACHE_TTL_*` overrides
- Commands: `uv add redis`, `uv sync --frozen`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Redis unavailable at runtime:** Mitigated by lazy connect + wrappers treating cache miss on errors (fall through to inner adapter).
- **Stub adapters + cache:** Tests use fake inner adapters with real cache wrappers; stub `NotImplementedError` tests remain unchanged on bare stubs.
- **Sync entrypoint vs async Redis:** Lazy async connect on first cache operation; no blocking ping in `main()`.

## Handoff to implementation

`IMPLEMENTATION1.md` should implement domain cache module first, then infrastructure adapters, then wiring/Settings, then tests and verification gates.
