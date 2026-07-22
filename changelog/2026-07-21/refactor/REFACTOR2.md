# Refactor Plan 2: Post-implementation full-system synthesis (AUDIT2)

**Date:** 2026-07-21
**Scope:** refactor (cross-cutting)
**Status:** final
**Source audits:**
- [PERFORMANCE_AUDIT2](../performance/PERFORMANCE_AUDIT2.md)
- [CODE_HEALTH_AUDIT2](../code-health/CODE_HEALTH_AUDIT2.md)

## Executive summary

AUDIT2 confirms same-day implementation closed most AUDIT1 wiring gaps: parallel `find_documents`, MCP tool cache, lazy LLM, shared Redis store, port-cache singleflight, workflow timeouts, and graph→workflow delegation. **Remaining work** clusters into four themes: **(1)** local UI bootstrap parity with `main.py` (H02, P13), **(2)** cache hardening on MCP-tool and LLM layers plus production cache enablement (P03, P05, P07, P08), **(3)** hot-path efficiency — duplicate YouTube calls, eager workflow wiring, per-invocation graph compile (P02, P04, P09, R03), and **(4)** BL-022 adapter implementation with HTTP timeouts and domain-mapped errors (H04, A02, P06). Estimated effort: **2–3 small PRs** for actionable non-BL-022 items; adapter work is a separate medium/large increment.

## Action summary

| ID | Action | Type | Location | Source IDs | Severity | Effort | Blocked by |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RF01 | Bootstrap local UI with composition root | WIRE | `local_ui_main.py:main` | H02, P13 | High | small | — |
| RF02 | Add singleflight to MCP tool cache | CONSOLIDATE | `mcp_tool_cache.py:get_or_invoke` | P03, D02 | High | small | — |
| RF03 | Cancel provisional YouTube task on title refinement | CHANGE | `workflows.py:retrieve_with_videos` | P02 | High | small | — |
| RF04 | Lazy-init `DocumentVideoWorkflow` at composition root | CHANGE | `wiring.py:initialize_application_runtime` | P04 | High | small | — |
| RF05 | Implement adapter HTTP bodies + timeouts | CHANGE | `infrastructure/*_client.py`, `groq_adapter.py` | H04, A02, P06 | High | large | BL-022 |
| RF06 | Add Groq client `timeout` / `max_retries` | CHANGE | `groq_adapter.py:build_groq_chat_model` | P06 | High | trivial | RF05 |
| RF07 | Add payload size guard to MCP tool cache | CHANGE | `mcp_tool_cache.py:get_or_invoke` | P08 | Medium | trivial | — |
| RF08 | Add singleflight to LLM cache miss path | CONSOLIDATE | `cached_llm.py:_agenerate` | P07, D02 | Medium | small | RF02 |
| RF09 | Memoize compiled graph (shared by run + registry) | CHANGE | `application/agent.py` | P09, R03 | Medium | small | — |
| RF10 | Extract `workflow_state_to_run_response` helper | CONSOLIDATE | `interface/validation.py` or helper | D01 | Medium | small | — |
| RF11 | Map uninitialized workflow to domain errors | CHANGE | `custom_tools.py`, `local_ui/api.py`, `agent.py:_require_workflow` | A01 | Medium | small | RF01 |
| RF12 | Use read retry policy on derive/merge nodes | CHANGE | `application/agent.py` | P12 | Medium | trivial | — |
| RF13 | Enforce `CACHE_ENABLED=true` in production deploy | DEFER | ops / `ENVIRONMENT_SETUP.md` | P05 | High | trivial | — |
| RF14 | Pick single cache boundary (port vs MCP) | DEFER | `custom_tools.py`, `cached_adapters.py` | P11 | Medium | medium | product decision |
| RF15 | Slim graph state to counts/summaries between nodes | DEFER | `application/agent.py:DocumentVideoState` | P10 | Medium | medium | product decision |
| RF16 | Document `run_workflow` vs `find_documents` latency trade-off | DEFER | tool descriptions / `AGENTIC_ARCHITECTURE.md` | P01, D03 | High | trivial | product decision |
| RF17 | Wire `build_search_client` into workflow/agent | DEFER | `wiring.py`, `workflows.py` or `agent.py` | H01 | Medium | medium | BL-022 |
| RF18 | First LLM graph node calling `get_chat_model()` | DEFER | `application/agent.py`, `llm.py` | H03, A04 | Medium | small | product decision |
| RF19 | Sync LLM cache path | DEFER | `cached_llm.py:_generate` | P17 | Low | small | sync caller exists |
| RF20 | Optional `VideoSummary` DTO for MCP responses | DEFER | `interface/validation.py` | P18 | Low | small | token pressure observed |
| RF21 | Export cache hit-rate at INFO or metrics backend | CHANGE | `cache_observability.py` | P16 | Low | small | — |

## Wire

### RF01: Bootstrap local UI with composition root

**Type:** WIRE
**Location:** `local_ui_main.py` (`main`)
**Source IDs:** H02, P13
**Severity:** High
**Effort:** small

**Current code:**

```python
def main() -> None:
    """Start the local FastAPI workflow UI on loopback only."""
    try:
        uvicorn.run(
            "mcp_server.interface.local_ui.api:app",
            host=local_ui_host(),
            port=local_ui_port(),
            reload=True,
            reload_dirs=["src"],
        )
```

**Target change:**

```python
from mcp_server.main import bootstrap_environment, configure_logging
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import load_settings
from mcp_server.wiring import initialize_application_runtime

def main() -> None:
    bootstrap_environment()
    settings = load_settings()
    configure_logging(settings)
    operational = load_operational_config()
    initialize_application_runtime(operational, settings)
    uvicorn.run(...)  # unchanged transport args
```

**Rationale:** Local UI POST `/api/workflows/{id}/run` calls `run_document_video_graph()` → `_require_workflow()`, which raises when `initialize_application_runtime()` was never called. MCP `main.py` already bootstraps; local UI diverges and cannot profile wired workflows.
**Verification after wire:** `pytest` for local UI POST run with fakes; manual `uv run python -m mcp_server.local_ui_main` then POST run succeeds.
**Depends on:** none

---

## Change

### RF03: Cancel provisional YouTube task on title refinement

**Type:** CHANGE
**Location:** `application/workflows.py:retrieve_with_videos` (lines 64–76)
**Source IDs:** P02
**Severity:** High
**Effort:** small

**Current code:**

```python
documents_task = asyncio.create_task(self.fetch_documents(query, document_limit))
videos_task = asyncio.create_task(self.search_videos(query, video_limit))
documents, provisional_videos = await asyncio.gather(documents_task, videos_task)

if not documents:
    return documents, provisional_videos

search_terms = self.derive_search_terms(query, documents)
if search_terms == query:
    return documents, provisional_videos

videos = await self.search_videos(search_terms, video_limit)
return documents, videos
```

**Target change:**

```python
documents_task = asyncio.create_task(self.fetch_documents(query, document_limit))
videos_task = asyncio.create_task(self.search_videos(query, video_limit))
documents = await documents_task

if not documents:
    videos = await videos_task
    return documents, videos

search_terms = self.derive_search_terms(query, documents)
if search_terms == query:
    videos = await videos_task
    return documents, videos

videos_task.cancel()
with contextlib.suppress(asyncio.CancelledError):
    await videos_task
videos = await self.search_videos(search_terms, video_limit)
return documents, videos
```

**Rationale:** When the first document title differs from the user query, the provisional YouTube call is wasted — up to 2× quota (`test_t19c`: `call_count == 2`). Await documents first; only keep parallel video when refinement is unnecessary.
**Verification after change:** `test_t19c` updated to expect single YouTube call on title-refinement path; parallel path still passes when `search_terms == query`.
**Depends on:** none

---

### RF04: Lazy-init `DocumentVideoWorkflow` at composition root

**Type:** CHANGE
**Location:** `wiring.py:initialize_application_runtime` (lines 220–225)
**Source IDs:** P04
**Severity:** High
**Effort:** small

**Current code:**

```python
cache_store = create_cache_store(settings)
configure_lazy_chat_model(settings, cache_store)
workflow = build_document_video_workflow(settings, cache_store)
tool_cache = build_mcp_tool_cache(settings, cache_store)
set_document_video_workflow(workflow)
set_mcp_tool_cache(tool_cache)
```

**Target change:** Mirror `configure_lazy_chat_model` — register a lazy builder that constructs `DocumentVideoWorkflow` on first `get_document_video_workflow()` access. `McpToolInteractionCache` can remain eager (lightweight) or lazy alongside workflow.

**Rationale:** Every MCP `main()` boot builds Supabase/YouTube adapters and workflow even when only `health_check` is used. Cold-start memory and client construction should defer until first tool that needs ports.
**Verification after change:** Boot with only `health_check` invocation — no adapter construction; first `find_documents` triggers build. Existing wiring tests pass.
**Depends on:** none

---

### RF05: Implement adapter HTTP bodies + timeouts

**Type:** CHANGE
**Location:** `infrastructure/supabase_client.py`, `youtube_client.py`, `search_client.py`
**Source IDs:** H04, A02, P06
**Severity:** High
**Effort:** large
**Blocked by:** BL-022

**Current code:**

```python
# supabase_client.py / youtube_client.py / search_client.py (pattern)
require_credential(...)
raise NotImplementedError("BL-022: adapter HTTP body not implemented")
```

**Target change:**

```python
# Example shape — align timeout with agent_node_timeout (60s) from config.json
async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
    response = await client.get(...)
# DuckDuckGo: asyncio.to_thread(sync_sdk.search, ...) if SDK is sync
# Map provider failures to DomainError subclasses (not NotImplementedError)
```

**Rationale:** Four MCP tools reach stub adapters at runtime; production calls fail with `NotImplementedError` instead of domain-mapped MCP errors. When bodies land, missing `timeout=` risks hung calls misaligned with `agent_node_timeout=60` s.
**Verification after change:** Adapter unit tests with `respx`/`httpx` mocks; MCP tool integration tests with fakes replaced by adapter fakes; no `NotImplementedError` on happy path.
**Depends on:** none (BL-022 product scope)

---

### RF06: Add Groq client `timeout` / `max_retries`

**Type:** CHANGE
**Location:** `infrastructure/groq_adapter.py:build_groq_chat_model`
**Source IDs:** P06
**Severity:** High
**Effort:** trivial
**Blocked by:** RF05 (ship with BL-022 hardening PR)

**Current code:**

```python
return ChatGroq(
    api_key=api_key,
    model=model_id,
    temperature=temperature,
)
```

**Target change:**

```python
return ChatGroq(
    api_key=api_key,
    model=model_id,
    temperature=temperature,
    timeout=60.0,
    max_retries=2,
)
```

**Rationale:** Groq inference has no explicit timeout today; should align with `agent_node_timeout` and port HTTP timeouts.
**Verification after change:** Unit test asserting `ChatGroq` receives timeout kwargs; LLM integration test with mocked provider.
**Depends on:** RF05

---

### RF07: Add payload size guard to MCP tool cache

**Type:** CHANGE
**Location:** `infrastructure/mcp_tool_cache.py:get_or_invoke` (line 45)
**Source IDs:** P08
**Severity:** Medium
**Effort:** trivial

**Current code:**

```python
result = await invoker()
await self._cache.set(key, McpToolCacheEnvelope.pack(result), rule.ttl_seconds)
return result
```

**Target change:**

```python
from mcp_server.infrastructure.cache_serialization import payload_within_cache_limit

result = await invoker()
payload = McpToolCacheEnvelope.pack(result)
if payload_within_cache_limit(payload):
    await self._cache.set(key, payload, rule.ttl_seconds)
return result
```

**Rationale:** Port adapters skip oversize payloads (`MAX_CACHE_PAYLOAD_BYTES = 512 KiB`); MCP layer has no guard — large `find_documents` / `run_workflow` responses can bloat Redis.
**Verification after change:** Test oversize tool result skips `cache.set`; normal payloads still cached.
**Depends on:** none

---

### RF09: Memoize compiled graph (shared by run + registry)

**Type:** CHANGE
**Location:** `application/agent.py:run_document_video_graph`, `_build_registered_workflows`
**Source IDs:** P09, R03
**Severity:** Medium
**Effort:** small

**Current code:**

```python
async def run_document_video_graph(...) -> DocumentVideoState:
    graph = create_agent()  # compile() every invocation
    ...

def _build_registered_workflows() -> list[RegisteredWorkflow]:
    return [RegisteredWorkflow(..., graph=build_document_video_graph()), ...]
```

**Target change:**

```python
_COMPILED_GRAPH: DocumentVideoGraph | None = None

def _get_compiled_graph() -> DocumentVideoGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_document_video_graph()
    return _COMPILED_GRAPH

async def run_document_video_graph(...) -> DocumentVideoState:
    graph = _get_compiled_graph()
    ...

def reset_compiled_graph_cache() -> None:
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None
```

**Rationale:** `StateGraph.compile()` runs on every `run_workflow` call; UI registry separately memoizes another compiled instance — two compiles for the same definition.
**Verification after change:** `test` asserting single compile across `run_document_video_graph` + `list_registered_workflows`; `reset_compiled_graph_cache()` for test isolation.
**Depends on:** none

---

### RF11: Map uninitialized workflow to domain errors

**Type:** CHANGE
**Location:** `interface/custom_tools.py`, `interface/local_ui/api.py`, `application/agent.py:_require_workflow`
**Source IDs:** A01
**Severity:** Medium
**Effort:** small

**Current code:**

```python
if workflow is None:
    msg = "Document video workflow has not been initialized"
    raise RuntimeError(msg)
```

**Target change:**

```python
from mcp_server.domain.exceptions import ResourceNotFoundError

if workflow is None:
    raise ResourceNotFoundError("Document video workflow has not been initialized")
```

Wire `ResourceNotFoundError` (or dedicated `ConfigurationError`) through `error_mapping.py` so `_cached_tool_invoke` maps it via `raise_as_mcp_error`, not generic 500.

**Rationale:** Misconfiguration surfaces as unmapped `RuntimeError` on hot MCP paths while `DomainError` paths get typed MCP errors.
**Verification after change:** Test uninitialized workflow returns mapped MCP error; local UI returns HTTP 503/404 per mapping policy.
**Depends on:** RF01 (local UI should not hit this in normal use)

---

### RF12: Use read retry policy on derive/merge nodes

**Type:** CHANGE
**Location:** `application/agent.py` (lines 49–52, 137–141)
**Source IDs:** P12
**Severity:** Medium
**Effort:** trivial

**Current code:**

```python
def _node_retry_policy() -> RetryPolicy:
    max_attempts = max(config.node_retries + 1, 1)  # → 4 with node_retries=3
    return RetryPolicy(max_attempts=max_attempts)

# merge_results uses merge_retry_policy = _node_retry_policy()
```

**Target change:** Use `_read_node_retry_policy()` (max_attempts=2) or `RetryPolicy(max_attempts=1)` for CPU-only `derive_search_terms` and `merge_results` nodes.

**Rationale:** Read nodes correctly cap retries; pure transform/merge nodes inherit full retry budget with no external I/O benefit.
**Verification after change:** Agent unit test asserts merge node `max_attempts`; existing graph tests pass.
**Depends on:** none

---

### RF21: Export cache hit-rate at INFO or metrics backend

**Type:** CHANGE
**Location:** `infrastructure/cache_observability.py`
**Source IDs:** P16
**Severity:** Low
**Effort:** small

**Current code:** `record_cache_hit` / `record_cache_miss` log at `DEBUG`; counters in-process only via `get_cache_metrics()`.

**Target change:** Periodic INFO log of hit-rate per operation type, or expose counters via a metrics hook. Correlate with `port_observability.py` spans.

**Rationale:** Hard to tune TTL or diagnose cache effectiveness in production when metrics are DEBUG-only and in-process.
**Verification after change:** Log capture test at INFO shows hit-rate after N cache operations.
**Depends on:** none

---

## Consolidate

### RF02: Add singleflight to MCP tool cache

**Type:** CONSOLIDATE
**Location:** `infrastructure/mcp_tool_cache.py:get_or_invoke`
**Source IDs:** P03, D02
**Severity:** High
**Effort:** small

**Current code:**

```python
record_cache_miss(operation.value, key)
result = await invoker()
await self._cache.set(key, McpToolCacheEnvelope.pack(result), rule.ttl_seconds)
return result
```

**Target change:** Route miss path through `run_cache_aside()` from `cache_aside.py`:

```python
return await run_cache_aside(
    cache=self._cache,
    key=key,
    rule=rule,
    operation=operation.value,
    span=PortCallSpan("mcp_tool", tool_name),  # or lightweight span
    serialize=McpToolCacheEnvelope.pack,
    deserialize=McpToolCacheEnvelope.unpack,
    loader=invoker,
)
```

**Rationale:** Port adapters use `CacheAsideCoordinator.singleflight`; MCP tool cache does not — concurrent identical tool calls duplicate full workflow work on cold keys.
**Verification after change:** Parallel miss test (mirror `test_c32`) invokes invoker once; hit path unchanged.
**Depends on:** none

---

### RF08: Add singleflight to LLM cache miss path

**Type:** CONSOLIDATE
**Location:** `infrastructure/cached_llm.py:_agenerate` (lines 128–135)
**Source IDs:** P07, D02
**Severity:** Medium
**Effort:** small

**Current code:**

```python
record_cache_miss(operation.value, key)
result = await self._inner._agenerate(...)
await self._cache.set(key, _serialize_chat_result(result), rule.ttl_seconds)
return result
```

**Target change:** Same `run_cache_aside()` pattern as RF02 with `_serialize_chat_result` / `_deserialize_chat_result` serializers.

**Rationale:** Concurrent identical LLM prompts duplicate Groq inference on cold keys; port cache already has stampede protection.
**Verification after change:** Parallel `_agenerate` miss test invokes inner model once.
**Depends on:** RF02 (establishes pattern)

---

### RF10: Extract `workflow_state_to_run_response` helper

**Type:** CONSOLIDATE
**Location:** `interface/custom_tools.py:_invoke_run_workflow`, `interface/local_ui/api.py:run_workflow`
**Source IDs:** D01
**Severity:** Medium
**Effort:** small

**Current code (duplicated in both files):**

```python
return WorkflowRunResponse(
    query=result["query"],
    search_terms=result["search_terms"],
    document_count=result["document_count"],
    video_count=result["video_count"],
    documents=document_hits_to_summaries(documents),
    videos=videos,
)
```

**Target change:** Add to `interface/validation.py`:

```python
def workflow_state_to_run_response(state: DocumentVideoState) -> WorkflowRunResponse:
    documents = state.get("documents", [])
    videos = state.get("videos", [])
    return WorkflowRunResponse(
        query=state["query"],
        search_terms=state["search_terms"],
        document_count=state["document_count"],
        video_count=state["video_count"],
        documents=document_hits_to_summaries(documents),
        videos=videos,
    )
```

**Rationale:** Response-shape changes require two edits today; MCP and local UI can drift.
**Verification after change:** Both call sites use helper; existing MCP and local UI response tests pass.
**Depends on:** none

---

## Deferred (do not implement in this refactor)

| ID | Source IDs | Location | Reason deferred | Revisit when |
| :--- | :--- | :--- | :--- | :--- |
| RF13 | P05 | `settings.py:cache_enabled`, deploy checklist | Ops/process change — `CACHE_ENABLED=false` default is intentional for dev; production requires explicit env | Staging/production deploy |
| RF14 | P11 | `custom_tools.py` + `cached_adapters.py` | Double cache layers when enabled — product must pick port vs MCP boundary | Cache strategy decision |
| RF15 | P10 | `agent.py:DocumentVideoState` | Slim state needs observability contract review | Graph observability requirements finalized |
| RF16 | P01, D03 | `custom_tools.py` tool descriptions | Intentional latency split (parallel `find_documents` vs sequential `run_workflow`) — document, don't merge | Tool UX review |
| RF17 | H01 | `wiring.py:build_search_client` | Web search not shipped (BL-005/BL-022); factory exists, zero production callers | `search_web` MCP tool lands |
| RF18 | H03, A04 | `llm.py:get_chat_model` | LLM stack wired but no production consumer | First LLM graph node ships |
| RF19 | P17 | `cached_llm.py:_generate` | No sync callers in production | Sync caller added |
| RF20 | P18 | `interface/validation.py` | `VideoSummary` DTO optional — bounded by `video_limit` ≤ 25 | Token pressure observed |

**No-remove items (keep as-is):**

| Source IDs | Location | Reason |
| :--- | :--- | :--- |
| R01 | `agent.py:create_agent` | Stable facade per `AGENTIC_ARCHITECTURE.md` growth path |
| R02 | `mcp_server.py:create_mcp_server` | Extension point for future multi-server config |
| R04 | `wiring.py:build_*` NoOp fallback | Harmless test-only path; document rather than remove |

## Recommended execution order

1. **RF01** — Unblock local UI workflow profiling and POST run tests.
2. **RF03** — Eliminate duplicate YouTube quota on common title-refinement path (small, high impact).
3. **RF02, RF07, RF08** — Cache hardening: MCP singleflight, payload cap, then LLM singleflight.
4. **RF04, RF09** — Boot and per-request efficiency: lazy workflow, memoized graph.
5. **RF10, RF11, RF12** — Maintainability: shared response helper, domain errors, retry policy.
6. **RF05, RF06** — BL-022 adapter bodies + timeouts (production blocker).
7. **RF21** — Observability polish.
8. **RF13–RF20** — Deferrals per product/ops decisions.

## Out of scope

- Live profiling against Supabase/YouTube/Groq (adapters are stubs until BL-022)
- SSE vs stdio transport comparison (P14)
- Local UI dev `reload=True` (P15)
- `ui/` frontend bundle performance
- `langchain_tools.py`, `parameter_builders.py`, SQL agent path (planned)
- Production load testing / benchmarking
- Documentation drift between `ARCHITECTURE.md` tree and on-disk layout

## Verdict

**ready with deferrals**

All High/Critical AUDIT2 findings have concrete actions or explicit deferrals. **13 implementable actions** (1 WIRE, 8 CHANGE, 4 CONSOLIDATE) can ship in 2–3 PRs without BL-022. **8 deferrals** require product, ops, or BL-022 scope. No layer-boundary violations proposed. Implement RF01, RF03, RF02 before production traffic with real backends; RF05/RF06 gate production readiness.
