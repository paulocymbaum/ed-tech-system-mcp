# Performance Audit 2: Full-system re-audit (post-implementation)

**Date:** 2026-07-21
**Scope:** performance (cross-cutting)
**Status:** final
**References:** [PERFORMANCE_AUDIT1](./PERFORMANCE_AUDIT1.md) (stale), [REFACTOR1](../refactor/REFACTOR1.md), same-day `IMPLEMENTATION*` increments (application, interface, infrastructure, entrypoint)

## Executive summary

Same-day implementation work resolved most AUDIT1 High findings: parallel `retrieve_with_videos`, MCP tool cache wiring, lazy LLM init, shared Redis store, port-cache singleflight, response pruning, workflow timeout enforcement, and basic observability (port-call spans, per-tool duration logs). The **live production surface is now four MCP tools** (`health_check`, `find_documents`, `search_youtube`, `run_workflow`), but **infrastructure adapters remain stubs** (`NotImplementedError`), so external I/O latency is not yet measurable.

Top remaining themes: **(1)** intentional latency split between fast parallel `find_documents` and slower sequential `run_workflow` graph path; **(2)** duplicate YouTube work on document-title refinement; **(3)** cache stampede gaps on MCP-tool and LLM cache layers; **(4)** eager workflow wiring at MCP boot; **(5)** forward-looking adapter HTTP timeout and sync-I/O risks before BL-022 ships.

## Delta from PERFORMANCE_AUDIT1

| AUDIT1 ID | AUDIT1 finding | Current state (2026-07-21 code) |
| :--- | :--- | :--- |
| P01 | Sequential I/O in `retrieve_with_videos` | **Resolved** — `asyncio.gather` + optional second YouTube call (`workflows.py:64–76`) |
| P02 | MCP tool cache unwired | **Resolved** — `initialize_application_runtime` → `set_mcp_tool_cache`; `_cached_tool_invoke` in `custom_tools.py` |
| P05 | Eager LLM at boot | **Resolved** — `configure_lazy_chat_model`; `get_chat_model()` builds on first access |
| P06 | Port cache stampede | **Resolved** — `run_cache_aside` + `CacheAsideCoordinator.singleflight` (`cache_aside.py`) |
| P07, P08 | Large cache/MCP payloads | **Resolved** — `cache_serialization.py` pruning/gzip; `DocumentSummary` in `validation.py` |
| P10 | Graph recompile per UI list | **Resolved** — `list_registered_workflows()` memoized (`agent.py:215–237`) |
| P11 | Duplicate Redis connections | **Resolved** — single `cache_store` in `ApplicationContext` (`wiring.py:220–230`) |
| P13 | Workflow timeout unwired | **Resolved** — `run_document_video_graph` → `ainvoke_with_workflow_timeout` |
| P04 | Retry amplification | **Partially mitigated** — read nodes use `max_attempts=2`; derive/merge still use full `node_retries + 1` |
| P03, P12, P14–P19 | Cache default off, sync LLM path, Groq timeout, etc. | **Still open** — see findings below |

## Baseline configuration

| Knob | Value | Notes |
| :--- | :--- | :--- |
| `workflow_timeout` | `300` s | `config.json` — enforced via `ainvoke_with_workflow_timeout` on `run_workflow` / local UI run |
| `agent_node_timeout` | `60` s | Per LangGraph node; wired on all four graph nodes |
| `node_retries` | `3` | → `RetryPolicy(max_attempts=4)` on derive/merge nodes; read nodes capped at `max_attempts=2` |
| `CACHE_ENABLED` | `false` (default) | `settings.py:24`; port + MCP + LLM wrappers skip cache unless env set |
| `CACHE_TTL_SUPABASE_FIND_DOCUMENTS` | `600` s (default rule) | `domain/cache.py` DEFAULT_CACHE_RULES |
| `CACHE_TTL_YOUTUBE_SEARCH_VIDEOS` | `3600` s (default rule) | Overridable via env |
| `CACHE_TTL_WEB_SEARCH` | `300` s (default rule) | Overridable via env |
| `CACHE_TTL_LLM_COMPLETION` | `3600` s (default rule) | Overridable via env |
| `CACHE_TTL_MCP_TOOL` | `60` s (default rule) | Overridable via env |
| `MAX_CACHE_PAYLOAD_BYTES` | `512 KiB` | Port adapters only (`cache_serialization.py:27`) |
| Transport | stdio (FastMCP) | `main.py` → `create_mcp_server().run()` |

## Hot paths reviewed

| Path | Entry point | Layers touched | Dominant cost driver |
| :--- | :--- | :--- | :--- |
| MCP `find_documents` | `custom_tools.py:find_documents` → `_cached_tool_invoke` | interface → application → ports → adapters | Parallel Supabase + YouTube I/O (when adapters ship); MCP tool cache hit/miss |
| MCP `search_youtube` | `custom_tools.py:search_youtube` | interface → application → `IVideoSearchClient` | YouTube API RTT + quota |
| MCP `run_workflow` | `custom_tools.py:run_workflow` → `run_document_video_graph` | interface → application (LangGraph) → ports | **Sequential** fetch → derive → search; graph compile per invocation |
| MCP `health_check` | `custom_tools.py:health_check` | interface only | Negligible |
| LangGraph agent | `agent.py:build_document_video_graph` | application | 4 sequential nodes; full `DocumentHit`/`VideoResult` lists in state |
| Cache-aside (ports) | `cached_adapters.py` → `run_cache_aside` | infrastructure | Redis RTT + serialize; singleflight on miss |
| Cache-aside (MCP) | `mcp_tool_cache.py` | infrastructure → interface | Redis RTT + `McpToolCacheEnvelope`; **no** singleflight |
| LLM (lazy, unused by graph) | `llm.py:get_chat_model` → `CachedChatModel` | application → infrastructure | Groq inference when first accessed; async cache only |
| Local UI list | `local_ui/api.py:list_workflows` | interface → application | Memoized graph metadata (one compile per process) |
| Local UI run | `local_ui/api.py:run_workflow` | interface → application | Same as MCP `run_workflow`; **no** composition-root bootstrap in `local_ui_main.py` |

---

## Findings

### Critical

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| — | — | — | No live path performs unbounded external I/O or blocks the event loop: adapters raise `NotImplementedError` after guard checks (`supabase_client.py:24`, `youtube_client.py:28`, `search_client.py:13`) | — | Re-audit when BL-022 implements HTTP clients; require explicit `timeout=` on all outbound HTTP and `asyncio.to_thread` or native async for DuckDuckGo if the SDK is sync | — |

### High

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P01 | app-sequential-io | `application/agent.py` + `custom_tools.py:run_workflow` | Graph path: `fetch_documents` → `derive_search_terms` → `search_videos` (sequential edges, lines 144–147). MCP `find_documents` uses parallel `retrieve_with_videos` instead | `run_workflow` wall-clock ≈ Supabase RTT + YouTube RTT (plus graph overhead); materially slower than `find_documents` for the same query | Document in tool descriptions that `run_workflow` trades latency for step visibility; or add a parallel terminal node that delegates to `retrieve_with_videos` when observability is not required | medium |
| P02 | Redundant external I/O | `application/workflows.py:retrieve_with_videos` | When documents exist and `documents[0].title != query`, issues parallel provisional YouTube search then a **second** `search_videos` with title (`test_t19c`: `call_count == 2`) | Up to **2× YouTube quota** and extra RTT on the common path where titles differ from user query | Cancel provisional video task when title refinement is needed; or skip parallel video start until documents return when title-based search is likely | small |
| P03 | infra-cache-stampede | `infrastructure/mcp_tool_cache.py:get_or_invoke` | Miss path calls `invoker()` with no `CacheAsideCoordinator` / lock (unlike `run_cache_aside` used by port wrappers) | Concurrent identical MCP tool calls duplicate full workflow work (Supabase + YouTube + serialize) on cold keys | Reuse `run_cache_aside` or `CacheAsideCoordinator.singleflight` in `McpToolInteractionCache` | small |
| P04 | entrypoint-eager-wiring | `wiring.py:initialize_application_runtime` | Every MCP `main()` builds `SupabaseRepository`, `YouTubeDataApiClient`, `DocumentVideoWorkflow`, and `McpToolInteractionCache` even when only `health_check` is used | Cold-start memory and client construction on every process boot; first real tool call does not pay wiring, but boot does | Lazy-init `DocumentVideoWorkflow` on first tool that needs it (mirror LLM lazy pattern) | small |
| P05 | Cache disabled by default | `settings.py:cache_enabled` (`default=False`) | `build_*` skip cache wrappers unless `CACHE_ENABLED=true` | Production without explicit env pays full external API cost on every request | Enforce `CACHE_ENABLED=true` + Redis in staging/production deploy checklist (documented in `ENVIRONMENT_SETUP.md`; not validated at startup) | trivial |
| P06 | infra-no-http-timeout (latent) | `infrastructure/supabase_client.py`, `youtube_client.py`, `search_client.py`, `groq_adapter.py` | Stubs today; no `httpx`/`googleapiclient` client with `timeout=`; `ChatGroq(...)` has no `timeout` or `max_retries` | When BL-022 lands, hung outbound calls can block until library defaults expire; misaligned with `agent_node_timeout=60` s | Add explicit HTTP timeouts aligned with `agent_node_timeout`; set Groq `timeout` in `groq_adapter.py` | medium |

### Medium

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P07 | infra-cache-stampede | `infrastructure/cached_llm.py:_agenerate` | Miss path: `await self._inner._agenerate(...)` with no singleflight (port cache has it; LLM cache does not) | Concurrent identical LLM prompts duplicate Groq inference on cold keys | Wrap LLM miss path with `CacheAsideCoordinator` (same helper as port cache) | small |
| P08 | Large values in Redis (MCP layer) | `infrastructure/cache_envelope.py:pack` | Serializes full tool results via `model_dump_json` with no `MAX_CACHE_PAYLOAD_BYTES` guard | Large `find_documents` / `run_workflow` responses can bloat Redis and network; port layer skips oversize payloads | Apply `payload_within_cache_limit` before `cache.set` in `McpToolInteractionCache` | trivial |
| P09 | Per-request graph compile | `application/agent.py:run_document_video_graph` | `graph = create_agent()` → `build_document_video_graph()` on **every** workflow invocation (lines 206–212); UI list memoization does not apply | CPU for `StateGraph.compile()` on each `run_workflow` call; adds fixed overhead atop I/O | Module-level memoize compiled graph (same pattern as `_REGISTERED_WORKFLOWS`) | trivial |
| P10 | Large state in graph | `application/agent.py:DocumentVideoState` | `documents: list[DocumentHit]` and `videos: list[VideoResult]` stored in graph state across nodes | LangGraph serializes full entities (including `content`) between nodes; memory + CPU on multi-node path | Store counts/summaries in state for observability nodes; pass full lists only to merge/output | medium |
| P11 | Duplicate cache layers | `custom_tools.py` + `cached_adapters.py` | With `CACHE_ENABLED=true`, MCP tool cache wraps entire tool output while port adapters cache individual Supabase/YouTube calls | Double Redis round-trips and JSON encode/decode on cache miss; stale-layer inconsistency if TTLs differ | Cache at one boundary only (prefer port adapters for granularity, or MCP layer for simplicity — not both for same data) | medium |
| P12 | Retry amplification (partial) | `application/agent.py` | `derive_search_terms` and `merge_results` use `_node_retry_policy()` (`max_attempts=4`); read nodes correctly use `_read_node_retry_policy()` (`max_attempts=2`) | CPU-only derive node can retry up to 4× on transient graph errors; low impact today | Use `_read_node_retry_policy()` or `max_attempts=1` for pure transform/merge nodes | trivial |
| P13 | entrypoint-missing-bootstrap | `local_ui_main.py` | Starts uvicorn without `bootstrap_environment` / `initialize_application_runtime`; `run_workflow` POST calls `_require_workflow()` which fails without runtime init | Local UI workflow runs cannot hit wired workflow; misleading perf testing without full stack | Mirror `main.py` bootstrap before `uvicorn.run` (see REFACTOR1 RF01) | small |

### Low

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P14 | MCP transport overhead | `main.py` | FastMCP stdio JSON-RPC per tool call | Minor vs external I/O at current scale | Acceptable; SSE only if multi-client concurrency needed | — |
| P15 | Local UI dev reload | `local_ui_main.py:19` | `reload=True` file watcher | Dev-only CPU; not production path | No action | — |
| P16 | Observability — cache metrics | `cache_observability.py` | Hit/miss logged at `DEBUG`; counters in-process only (`get_cache_metrics`) | Hard to tune TTL or diagnose cache effectiveness in production | Export hit-rate at INFO or metrics backend; correlate with port/MCP spans | small |
| P17 | LLM sync path bypasses cache | `cached_llm.py:_generate` | Sync `_generate` delegates without cache (documented) | No production sync callers today | Defer until sync caller exists | — |
| P18 | interface-large-payload (video) | `interface/validation.py` | `VideoSearchResponse` / `DocumentQueryResponse` return full `VideoResult` list (no summary DTO unlike `DocumentSummary`) | Moderate JSON-RPC size vs documents; bounded by `video_limit` ≤ 25 | Optional `VideoSummary` DTO if token pressure observed | small |

---

## Positive patterns observed

- **Parallel composite I/O** on MCP `find_documents` via `asyncio.gather` with documented title-refinement trade-off (`workflows.py`)
- **MCP tool cache wired** at composition root with per-tool `duration_ms` logging (`custom_tools.py:_cached_tool_invoke`)
- **Lazy LLM construction** — no Groq client built at MCP boot (`configure_lazy_chat_model`, `get_chat_model`)
- **Single shared `ICacheStore`** in `ApplicationContext` (no duplicate Redis clients)
- **Port-cache singleflight** on miss (`cache_aside.py`); verified by `test_c32_parallel_misses_invoke_inner_port_once`
- **Cache payload pruning, gzip, and size guard** on port adapters (`cache_serialization.py`)
- **MCP document response pruning** via `DocumentSummary` / `document_hits_to_summaries`
- **Workflow timeout enforced** on graph invocations (`ainvoke_with_workflow_timeout`)
- **Per-node timeouts and differentiated retry** on read vs merge nodes (`agent.py`)
- **Port-call timing spans** at INFO (`port_observability.py`); integrated in `cached_adapters.py`
- **Redis graceful degradation** — lazy connect, miss on failure (`redis_cache_store.py`)
- **Stable cache keys** — `_canonicalize` + SHA-256 (`domain/cache.py`)
- **Bounded request limits** — Pydantic caps on MCP tools (`document_limit` ≤ 50, `video_limit` ≤ 25)
- **Memoized workflow registry** for local UI listing (`list_registered_workflows`)

## Observability gaps

- No distributed trace / correlation IDs across LangGraph nodes or MCP → port boundaries
- Cache hit/miss for MCP tool and LLM layers logged at DEBUG only (`cache_observability.py`); no exportable hit-rate metric in production logs
- No alerting on workflow timeout (`asyncio.TimeoutError` from `ainvoke_with_workflow_timeout`) or retry exhaustion
- Per-port spans exist; no breakdown inside stub adapters (Supabase query vs map) — blocked on BL-022
- `run_workflow` vs `find_documents` latency not distinguishable in a single metric dimension (different tools, different log lines only)

## Recommended remediation order

1. **Before BL-022 adapter merge (P06)** — HTTP timeouts on Supabase/YouTube/search; async-safe DuckDuckGo integration.
2. **Before production traffic (P05, P03, P04)** — Enable cache in prod; add MCP-tool singleflight; consider lazy workflow wiring.
3. **Tool-path clarity (P01, P02)** — Document or align `run_workflow` vs `find_documents` latency; reduce duplicate YouTube calls on title refinement.
4. **Cache hardening (P07, P08, P11)** — Singleflight on LLM cache; payload cap on MCP cache; pick one cache boundary.
5. **Graph efficiency (P09, P10, P12)** — Memoize compiled graph; slim graph state; tune retry on CPU nodes.
6. **Local dev parity (P13)** — Bootstrap `local_ui_main.py` for realistic workflow profiling.

## Out of scope / deferred

- Live profiling against Supabase/YouTube/Groq (adapters are stubs)
- SSE vs stdio transport comparison
- `ui/` frontend bundle performance
- SQL agent path, `langchain_tools.py`, `parameter_builders.py` (planned)
- Production load testing / benchmarking
- Sync LLM cache path (P17) until a sync caller exists

## Verdict

**acceptable with known risks**

AUDIT1’s highest-impact wiring gaps are **closed in current code**. The MCP surface is live with caching, parallel document+video I/O on `find_documents`, and basic timing observability. **No Critical incidents** exist today because external adapters do not perform I/O. Remaining High findings are **real for the wired tool paths** (sequential `run_workflow`, duplicate YouTube on refinement, MCP-cache stampede, eager workflow boot, cache-off default) and **latent for adapter implementation** (HTTP timeouts). Address P03, P05, P06, and P02 before exposing production traffic with real Supabase/YouTube backends.
