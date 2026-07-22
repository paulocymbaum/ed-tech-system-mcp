# Performance Audit 1: Full-system latency and resource scan

**Date:** 2026-07-21
**Scope:** performance (cross-cutting)
**Status:** final
**References:** [code-health/CODE_HEALTH_AUDIT1.md](../code-health/CODE_HEALTH_AUDIT1.md), [application/CODE_REVIEW1.md](../application/CODE_REVIEW1.md), [infrastructure/CODE_REVIEW1.md](../infrastructure/CODE_REVIEW1.md), `AGENTIC_ARCHITECTURE.md`

## Executive summary

Current production surface is minimal (`health_check` MCP tool only), so **no Critical hot-path incidents exist today**. The dominant future risk is the **document+video workflow path**: when adapters and MCP tools ship, latency will sum across sequential Supabase → YouTube I/O, graph retries will amplify tail latency, and caching/tool wrappers are not yet wired at the interface boundary. Secondary risks are **eager startup wiring** (LLM + optional Redis on every `main()` boot) and **missing observability** (no timing spans, cache hit-rate metrics, or per-tool latency breakdown).

## Baseline configuration

| Knob | Value | Notes |
| :--- | :--- | :--- |
| `workflow_timeout` | `300` s | `config.json` — overall graph budget |
| `agent_node_timeout` | `60` s | Per LangGraph node cap |
| `node_retries` | `3` | → `RetryPolicy(max_attempts=4)` per node |
| `CACHE_ENABLED` | `false` (default) | `settings.py`; no cache-aside unless env set |
| `CACHE_TTL_SUPABASE_FIND_DOCUMENTS` | `600` s (default rule) | Overridable via env |
| `CACHE_TTL_YOUTUBE_SEARCH_VIDEOS` | `3600` s (default rule) | Overridable via env |
| `CACHE_TTL_WEB_SEARCH` | `300` s (default rule) | Overridable via env |
| `CACHE_TTL_LLM_COMPLETION` | `3600` s (default rule) | Overridable via env |
| `CACHE_TTL_MCP_TOOL` | `60` s (default rule) | Overridable via env |
| Transport | stdio (FastMCP default) | `main.py` → `create_mcp_server().run()`; single-process JSON-RPC |

## Hot paths reviewed

| Path | Entry point | Layers touched | Dominant cost driver |
| :--- | :--- | :--- | :--- |
| MCP `health_check` | `custom_tools.py` | interface only | Negligible (string return) |
| Document+video workflow (planned) | `workflows.py:retrieve_with_videos` | application → ports → adapters | Sequential Supabase + YouTube I/O |
| LangGraph agent (skeleton) | `agent.py:build_document_video_graph` | application | 4 sequential nodes × retry policy; no real I/O yet |
| LLM completion (wired, unused by graph) | `wiring.build_chat_model` → `CachedChatModel` | entrypoint → infrastructure | Groq inference; cache optional |
| Local UI workflow list | `local_ui/api.py` → `list_registered_workflows` | interface → application | Graph recompilation per request |
| Cache-aside (when enabled) | `cached_adapters.py`, `cached_llm.py`, `mcp_tool_cache.py` | infrastructure | Redis round-trips + JSON serialize/deserialize |

---

## Findings

### Critical

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| — | — | — | No production path today performs unbounded external I/O, blocks the event loop with sync HTTP, or lacks any timeout on live adapters (stubs raise `NotImplementedError`) | — | Re-audit when `supabase_client.py`, `youtube_client.py`, `search_client.py` are implemented; require `httpx` timeouts on all HTTP clients | — |

### High

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P01 | app-sequential-io | `application/workflows.py:retrieve_with_videos` | `documents = await self._repository.find_documents(...)` then `videos = await self._video_client.search_videos(...)` — no `asyncio.gather` | Wall-clock latency = Supabase RTT + YouTube RTT on every workflow call; dominant cost when adapters ship | When title fallback is not needed (empty docs or query-only path), fire both calls in parallel via `asyncio.gather`; keep sequential only when first doc title is required | small |
| P02 | Missing MCP tool cache | `interface/custom_tools.py`, `infrastructure/mcp_tool_cache.py` | Only `health_check` registered; `McpToolInteractionCache.get_or_invoke()` exists but `build_mcp_tool_cache()` is never called from entrypoint | Identical MCP tool args will re-hit Supabase/YouTube on every call when tools ship | Wire `build_mcp_tool_cache()` at composition root; wrap tool handlers with `get_or_invoke(tool_name, args, invoker)` | medium |
| P03 | Cache disabled by default | `settings.py:cache_enabled` (`default=False`) | `build_*` factories skip cache wrappers unless `CACHE_ENABLED=true` | Production deployments without explicit env pay full external API cost on every request | Document prod requirement to set `CACHE_ENABLED=true` + Redis; consider opt-in per environment in deployment checklist | trivial |
| P04 | Retry amplification | `application/agent.py` + `config.json` | `RetryPolicy(max_attempts=node_retries + 1)` = 4 attempts/node; graph has 4 sequential nodes | Worst-case tail = 4 nodes × 4 attempts × 60 s node timeout = 960 s theoretical (capped only if `ainvoke_with_workflow_timeout` is used — it is not wired) | Wire `ainvoke_with_workflow_timeout()` for graph invocations; consider lower `node_retries` on read-only external calls; use idempotency-aware retry classification | small |
| P05 | Eager wiring at startup | `main.py` → `initialize_application_runtime(operational, _settings)` → `build_chat_model()` | Every MCP boot builds Groq client and optionally `CachedChatModel` + `RedisCacheStore` even when only `health_check` is used | Cold-start latency includes LLM factory + potential Redis `ping()` on first cache op; memory for unused clients | Lazy-init chat model on first agent/LLM call, or gate `build_chat_model()` behind feature flag | small |

### Medium

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P06 | Cache-aside stampede | `infrastructure/cached_adapters.py` (all 3 wrappers) | On cache miss, no lock/singleflight; concurrent requests with same key all call inner adapter | Thundering herd on cold keys; duplicate Supabase/YouTube quota burn under concurrent load | Add per-key asyncio lock or singleflight wrapper in cache-aside helper before inner call | medium |
| P07 | JSON serialize on cache hot path | `cached_adapters.py`, `cached_llm.py` | Every miss: `model_dump()` + `json.dumps()` for full document/video lists; LLM cache serializes all message payloads | CPU + allocation proportional to result size; large document `content` fields amplify cost | Prune fields before cache write; consider compression for large lists; cap cached payload size | small |
| P08 | Large MCP response payloads (latent) | `domain/schemas.py:DocumentHit` | `content: str` included in entity returned through workflow → MCP boundary | Full document bodies in JSON-RPC responses increase host token pressure and transport time | Add response DTO at interface layer with field pruning (`id`, `title`, snippet only) | small |
| P09 | Deep graph for simple retrieval | `application/agent.py` | 4 nodes (`fetch_documents` → `derive_search_terms` → `search_videos` → `merge_results`) for stub logic returning counts | Graph overhead (state serialization between nodes) without parallel benefit today | Collapse to fewer nodes when integrating real port calls; or use `DocumentVideoWorkflow` as single node | medium |
| P10 | Graph recompilation per UI request | `interface/local_ui/api.py:_workflow_index` | Calls `list_registered_workflows()` → `build_document_video_graph()` on every `/api/workflows` hit | Dev-only path; unnecessary CPU per page load | Cache compiled graph at module level or memoize `list_registered_workflows()` result | trivial |
| P11 | Duplicate Redis connections (latent) | `wiring.py` | `build_document_video_workflow()`, `build_mcp_tool_cache()`, `build_chat_model()` each call `create_cache_store()` independently | 3 Redis connections when all paths active | Share single `ICacheStore` instance from composition root | small |
| P12 | LLM sync path bypasses cache | `infrastructure/cached_llm.py:_generate` | Sync `_generate` delegates to inner without cache; only `_agenerate` is cached | Sync callers pay full inference cost every time | Document async-only contract; or add sync cache path if sync callers are introduced | trivial |
| P13 | Workflow timeout not enforced | `application/agent.py:ainvoke_with_workflow_timeout` | Helper exists with `asyncio.wait_for(..., timeout=workflow_timeout_seconds())` but zero production/test callers outside definition | Graph runs without overall timeout enforcement today | Call from MCP `run_workflow` tool and local UI execution path when added | small |
| P14 | agent_node_timeout vs I/O budget | `config.json` | `agent_node_timeout=60` s per node; realistic Supabase+YouTube+retry could exceed per-node budget | Nodes timeout before completing real I/O when adapters ship | Tune timeouts after adapter profiling; document expected P99 per port | small |

### Low

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P15 | Stdio transport overhead | `main.py` | FastMCP stdio JSON-RPC framing per tool call | Minor vs external I/O; relevant only at very high call rates | Acceptable for current scale; consider SSE only if concurrent clients needed | — |
| P16 | Local UI dev reload | `local_ui_main.py` | `uvicorn.run(..., reload=True)` | Dev-only overhead; file watcher CPU | No action for production (separate entrypoint) | — |
| P17 | Cache key stability | `domain/cache.py:build_cache_key` | `_canonicalize()` sorts dict keys; SHA-256 digest | Keys are stable — positive; minor hash CPU per cache op | No change needed | — |
| P18 | Port default limits | `domain/interfaces.py`, `workflows.py` | `document_limit=10`, `video_limit=5`, `max_results=5` | Bounded reads — positive pattern | Keep defaults; expose as tool params with same caps | — |
| P19 | Groq adapter no explicit timeout | `infrastructure/groq_adapter.py` | `ChatGroq(...)` without `timeout=` or `max_retries=` | Relies on library defaults; may differ from `agent_node_timeout` | Set explicit `timeout` aligned with `agent_node_timeout` when profiling Groq latency | trivial |

---

## Positive patterns observed

- Cache-aside architecture with deterministic keys (`build_cache_key` + `_canonicalize`) and per-operation TTL defaults
- `RedisCacheStore` lazy-connects and degrades gracefully (no crash on Redis down; treats as cache miss)
- LangGraph nodes have per-node `timeout` and `RetryPolicy` wired from `WorkflowExecutionConfig`
- Port signatures include bounded `limit` / `max_results` defaults
- `NoOpCacheStore` avoids Redis overhead when `CACHE_ENABLED=false`
- Async port contracts throughout (`async def find_documents`, etc.) — no sync-blocking adapters yet
- `CachedChatModel` caches async completions with full message payload in key (correct semantics for cache hits)

## Observability gaps

- No structured timing spans on port calls (Supabase, YouTube, web search)
- No cache hit/miss metrics or logging in `cached_adapters.py` (implicit only via inner call count in tests)
- No per-MCP-tool latency breakdown
- `log_level` setting exists but no logging bootstrap consumes it — cannot tune log verbosity for perf debugging
- No distributed trace IDs across workflow nodes
- No alerting on retry exhaustion or workflow timeout events

## Recommended remediation order

1. **Before shipping MCP tools (P02, P05, P13)** — Wire `McpToolInteractionCache`, lazy-init LLM, enforce `ainvoke_with_workflow_timeout()`.
2. **When implementing adapters (P01, future Critical)** — Add HTTP timeouts; profile sequential vs parallel I/O; enable `CACHE_ENABLED` in prod.
3. **Before concurrent load (P06, P11)** — Add cache stampede protection; share single Redis connection at composition root.
4. **At interface boundary (P08)** — Prune `DocumentHit` fields in MCP response schemas.
5. **After adapter profiling (P04, P14, P19)** — Tune `node_retries`, `agent_node_timeout`, and Groq timeout to measured P99.
6. **Observability** — Add port-call timing logs and cache hit-rate counters before production hardening.

## Out of scope / deferred

- Live profiling against Supabase/YouTube/Groq (adapters are stubs)
- SSE vs stdio transport comparison (single stdio client assumed)
- `ui/` frontend bundle performance
- SQL agent path and `parameter_builders.py` (planned, not implemented)
- Production load testing / benchmarking

## Verdict

**acceptable with known risks**

The system is performance-safe for its current `health_check`-only surface. Risks are **forward-looking**: sequential I/O, unwired caching, retry amplification, and eager startup wiring will matter as soon as document/video tools and real adapters ship. No Critical findings today because hot paths are stubs or unwired; prioritize P01–P05 before exposing MCP tools to production traffic.
