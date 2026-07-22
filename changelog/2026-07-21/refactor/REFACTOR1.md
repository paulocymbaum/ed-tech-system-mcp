# Refactor Plan 1: Full-system audit synthesis (performance + code health)

**Date:** 2026-07-21
**Scope:** refactor (cross-cutting)
**Status:** final
**Source audits:**
- [PERFORMANCE_AUDIT1](../performance/PERFORMANCE_AUDIT1.md)
- [CODE_HEALTH_AUDIT1](../code-health/CODE_HEALTH_AUDIT1.md)

## Executive summary

The 2026-07-21 audits captured the scaffold at **health-check-only MCP** with parallel unwired paths. Subsequent same-day increments (entrypoint IMPLEMENTATION3–4, application IMPLEMENTATION1, infrastructure IMPLEMENTATION2–3, domain IMPLEMENTATION1) **resolved most High findings**: shared `ICacheStore`, MCP tool cache wiring, lazy LLM init, graph→workflow delegation, parallel `retrieve_with_videos`, workflow timeout enforcement, logging bootstrap, response DTO pruning, cache stampede protection on port adapters, and deletion of `external_apis.py`.

**Remaining work** concentrates on three themes: (1) **local UI entrypoint** missing composition-root bootstrap, (2) **cache singleflight gaps** on MCP-tool and LLM cache paths, and (3) **forward-looking hardening** (Groq timeouts, adapter HTTP timeouts, domain exceptions in adapter bodies) blocked on BL-022 adapter implementation. Estimated effort: **2–3 small PRs** for actionable items; deferrals revisit when adapters ship.

## Resolved since audit (no action required)

| Source IDs | Finding | Resolution evidence |
| :--- | :--- | :--- |
| P01 | Sequential I/O in `retrieve_with_videos` | `workflows.py` uses `asyncio.gather` with title-fallback path |
| P02, H02, H09 | Unwired MCP tool cache | `initialize_application_runtime` + `_cached_tool_invoke` in `custom_tools.py` |
| P03 | Cache disabled by default | Documented in `ENVIRONMENT_SETUP.md` § production cache checklist |
| P05 | Eager LLM at boot | `configure_lazy_chat_model` + `get_chat_model()` lazy build |
| P07, P08 | Large cache/MCP payloads | `cache_serialization.py` pruning; `DocumentSummary` in `validation.py` |
| P10 | Graph recompilation per UI request | `list_registered_workflows()` memoized (`_REGISTERED_WORKFLOWS`) |
| P11, R03 | Duplicate Redis connections | Single `cache_store` in `ApplicationContext` |
| P12 | LLM sync path bypasses cache | Documented async-only contract in `cached_llm.py` |
| P13, H05 | `ainvoke_with_workflow_timeout` unwired | Called from `run_document_video_graph` |
| H03, R04 | `external_apis.py`, empty `TYPE_CHECKING` | File deleted (BL-025); `cache_config.py` cleaned |
| H04, D01, A01 | Dual orchestration paths | Graph nodes delegate to `DocumentVideoWorkflow` |
| H06 | Stale `log_level` | `configure_logging()` in `main.py` |
| H08 | Unused validation schemas | `search_youtube`, `find_documents`, `run_workflow` tools wired |
| D03, D04 | Cache duplication / config drift | `run_cache_aside()` helper; `DEFAULT_WORKFLOW_EXECUTION_CONFIG` loads `config.json` |
| A05 | `json.dumps(default=str)` in MCP cache | `McpToolCacheEnvelope.pack/unpack` |

## Action summary

| ID | Action | Type | Location | Source IDs | Severity | Effort | Blocked by |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RF01 | Bootstrap local UI entrypoint with settings + runtime init | WIRE | `local_ui_main.py` | H02 (local_ui row), P13 | High | small | — |
| RF02 | Extend singleflight to MCP tool and LLM cache paths | CONSOLIDATE | `mcp_tool_cache.py`, `cached_llm.py` | P06 | Medium | small | — |
| RF03 | Enforce shared cache store in builders (no silent fallback) | CHANGE | `wiring.py:build_*` | P11, R03 | Medium | trivial | — |
| RF04 | Add explicit Groq client timeout | CHANGE | `groq_adapter.py` | P19, P14 | Medium | trivial | — |
| RF05 | Classify read vs merge node retries (document policy) | CHANGE | `application/agent.py` | P04 | Medium | trivial | — |
| RF06 | Raise domain exceptions from adapter stubs at guard sites | CHANGE | `infrastructure/*_client.py` | H07, A03 | Medium | small | BL-022 |
| RF07 | Add `httpx` timeouts to HTTP adapters | CHANGE | `infrastructure/*_client.py` | Critical (forward), P14 | High | medium | BL-022 |
| RF08 | Wire `build_search_client` into workflow/agent | WIRE | `wiring.py`, `workflows.py` or `agent.py` | H01 | High | medium | BL-022 |
| RF09 | Distributed trace IDs + retry/timeout alerting | CHANGE | `port_observability.py`, `agent.py` | Observability gaps | Low | medium | — |
| RF10 | Collapse graph nodes when observability not needed | DEFER | `application/agent.py` | P09 | Low | medium | product decision |
| RF11 | Production cache env validation in deploy checklist | DEFER | ops / Doppler | P03 | Low | trivial | — |
| RF12 | Sync LLM cache path | DEFER | `cached_llm.py` | P12 | Low | small | sync caller exists |

## Wire

### RF01: Bootstrap local UI entrypoint with settings + runtime init

**Type:** WIRE
**Location:** `local_ui_main.py` (`main`)
**Source IDs:** H02 (import baseline: `local_ui_main.py` row), P13
**Severity:** High
**Effort:** small

**Current code:**

```python
def main() -> None:
  """Start the local FastAPI workflow UI on loopback only."""
  try:
    uvicorn.run(
      "mcp_server.interface.local_ui.api:app",
      ...
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
  uvicorn.run(...)
```

**Rationale:** Local UI calls `run_document_video_graph` → `_require_workflow()` which raises when `set_document_video_workflow` was never called. MCP `main.py` bootstraps correctly; local UI does not — audit import baseline gap persists.
**Verification after change:** `uv run pytest tests/interface/test_local_ui_api.py`; add test that POST `/api/workflows/document-video-discovery/run` succeeds with fakes after bootstrap.
**Depends on:** none

---

## Consolidate

### RF02: Extend singleflight to MCP tool and LLM cache paths

**Type:** CONSOLIDATE
**Location:** `infrastructure/mcp_tool_cache.py` (`get_or_invoke`), `infrastructure/cached_llm.py` (`_agenerate`)
**Source IDs:** P06
**Severity:** Medium
**Effort:** small

**Current code (`mcp_tool_cache.py`):**

```python
record_cache_miss(operation.value, key)
result = await invoker()
await self._cache.set(key, McpToolCacheEnvelope.pack(result), rule.ttl_seconds)
return result
```

**Target change:** Reuse `run_cache_aside` or `CacheAsideCoordinator.singleflight` from `cache_aside.py` on miss paths so concurrent identical tool/LLM keys invoke the inner delegate once (port adapters already use this pattern).

**Rationale:** P06 stampede protection is implemented for `CachedDataRepository` / search / video wrappers but not MCP-tool or LLM cache layers.
**Verification after change:** Concurrent miss tests in `tests/test_cache.py` for `McpToolInteractionCache` and `CachedChatModel`.
**Depends on:** none

---

## Change

### RF03: Enforce shared cache store in builders (no silent fallback)

**Type:** CHANGE
**Location:** `wiring.py` (`build_document_video_workflow`, `build_mcp_tool_cache`, `build_chat_model`)
**Source IDs:** P11, R03
**Severity:** Medium
**Effort:** trivial

**Current code:**

```python
store = cache if cache is not None else create_cache_store(settings)
```

**Target change:**

```python
if settings.cache_enabled and cache is None:
    raise ValueError(_CACHE_STORE_REQUIRED_MSG)
store = cache if cache is not None else NoOpCacheStore()
```

Apply the same pattern already used at the top of `build_document_video_workflow` / `build_mcp_tool_cache` to eliminate the `create_cache_store` fallback on line 178/196 — direct builder calls must not spawn extra Redis connections.

**Rationale:** Composition root guarantees single store; fallback undermines P11/R03 remediation when builders are called outside `initialize_application_runtime`.
**Verification after change:** `uv run pytest tests/test_cache.py::test_c21_initialize_application_runtime_creates_single_cache_store`; add test that `build_document_video_workflow(settings, cache=None)` with `cache_enabled=True` raises.
**Depends on:** none

---

### RF04: Add explicit Groq client timeout

**Type:** CHANGE
**Location:** `infrastructure/groq_adapter.py` (`build_groq_chat_model`)
**Source IDs:** P19, P14
**Severity:** Medium
**Effort:** trivial

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
from mcp_server.application.workflow_config import get_workflow_execution_config

timeout = get_workflow_execution_config().agent_node_timeout_seconds
return ChatGroq(
    api_key=api_key,
    model=model_id,
    temperature=temperature,
    timeout=timeout,
    max_retries=1,
)
```

Pass timeout via builder lambda from `wiring.py` if runtime config may be unset during unit tests.

**Rationale:** Groq inference currently relies on library defaults; misalignment with `agent_node_timeout` can cause hung nodes or premature graph timeouts.
**Verification after change:** `uv run pytest tests/test_llm.py`; mock `ChatGroq` kwargs assertion.
**Depends on:** none

---

### RF05: Classify read vs merge node retries (document policy)

**Type:** CHANGE
**Location:** `application/agent.py` (`build_document_video_graph`)
**Source IDs:** P04
**Severity:** Medium
**Effort:** trivial

**Current code:** `_read_node_retry_policy()` uses `max_attempts=2`; `derive_search_terms` and `merge_results` still use `_node_retry_policy()` (`node_retries + 1` = 4).

**Target change:** Keep read-only port nodes (`fetch_documents`, `search_videos`) on `_read_node_retry_policy()`. Move pure in-process nodes (`derive_search_terms`, `merge_results`) to `RetryPolicy(max_attempts=1)` — no external I/O to retry.

**Rationale:** P04 tail latency = 4 nodes × 4 attempts × 60 s without this split; read path is already partially fixed.
**Verification after change:** `uv run pytest tests/test_llm.py`; assert retry policy per node in graph metadata test.
**Depends on:** none

---

### RF06: Raise domain exceptions from adapter stubs at guard sites

**Type:** CHANGE
**Location:** `infrastructure/supabase_client.py`, `search_client.py`, `youtube_client.py`
**Source IDs:** H07, A03
**Severity:** Medium
**Effort:** small

**Current code:** Guards call `domain/invariants.py` (raises `DomainValidationError` / `ResourceNotFoundError`); method body still ends with `raise NotImplementedError(...)`.

**Target change:** When BL-022 implements HTTP logic, map provider errors to `ResourceNotFoundError` / `DomainValidationError` and remove bare `NotImplementedError` from production paths. Until then, ensure `NotImplementedError` is never reachable from MCP tools without a feature flag — tools already call workflow which hits stubs.

**Rationale:** H07 — exception taxonomy exists but adapters do not emit domain errors on failure paths.
**Verification after change:** `uv run pytest tests/`; `rg "raise NotImplementedError" src/mcp_server/infrastructure`.
**Depends on:** BL-022 adapter implementation

---

### RF07: Add `httpx` timeouts to HTTP adapters

**Type:** CHANGE
**Location:** `infrastructure/supabase_client.py`, `search_client.py`, `youtube_client.py`
**Source IDs:** Performance audit Critical (forward-looking), P14
**Severity:** High
**Effort:** medium

**Current code:** Stubs raise `NotImplementedError` — no HTTP client yet.

**Target change:** When implementing adapters, use `httpx.AsyncClient(timeout=httpx.Timeout(...))` with connect/read limits ≤ `agent_node_timeout_seconds` from `WorkflowExecutionConfig`.

**Rationale:** Performance audit Critical row — unbounded external I/O is the top future risk when stubs are replaced.
**Verification after change:** Adapter contract tests with timeout simulation; no unbounded `await client.get(...)`.
**Depends on:** BL-022

---

### RF09: Distributed trace IDs + retry/timeout alerting

**Type:** CHANGE
**Location:** `infrastructure/port_observability.py`, `application/agent.py`
**Source IDs:** Performance audit § Observability gaps
**Severity:** Low
**Effort:** medium

**Current code:** `port_call_span` logs `operation`, `duration_ms`, `cache` at INFO; MCP tools log per-tool latency in `custom_tools.py`.

**Target change:** Propagate a `workflow_run_id` (UUID) through graph state and include in port/MCP log lines; log WARNING on `RetryPolicy` exhaustion and `asyncio.TimeoutError` from `ainvoke_with_workflow_timeout`.

**Rationale:** Partial observability exists; gaps are correlation across nodes and alertable retry/timeout events.
**Verification after change:** Log capture tests; manual local UI run shows consistent `workflow_run_id`.
**Depends on:** RF01 (local UI should bootstrap before trace validation)

---

## Deferred (do not implement in this refactor)

| ID | Source IDs | Location | Reason deferred | Revisit when |
| :--- | :--- | :--- | :--- | :--- |
| RF08 | H01 | `wiring.py:build_search_client` | Explicit deferral documented (`# deferred — web search`); BL-005 closed | BL-022 DuckDuckGo adapter + `search_web` MCP tool ship |
| RF10 | P09 | `application/agent.py` | Sequential graph is intentional for local UI traces and per-node observability; `retrieve_with_videos` covers parallel MCP path | Product chooses single-node graph or observability via spans only |
| RF11 | P03 | Deployment / Doppler | `ENVIRONMENT_SETUP.md` already documents `CACHE_ENABLED=true` for prod; no code change | Staging/prod Doppler configs validated |
| RF12 | P12 | `cached_llm.py:_generate` | Async-only contract documented; no sync callers in production | A sync LangChain caller is introduced |

## Recommended execution order

1. **RF01** — Unblocks local UI workflow execution and validates graph wiring end-to-end.
2. **RF03** — Locks single-store invariant before expanding cache usage.
3. **RF02** — Closes stampede gap on MCP-tool/LLM paths under concurrent load.
4. **RF04, RF05** — Low-effort timeout/retry alignment before adapters ship.
5. **RF06, RF07, RF08** — Bundle with BL-022 adapter implementation PR.
6. **RF09** — Observability polish after RF01 provides a second entrypoint to test traces.

## Out of scope

- Implementing Supabase/YouTube/DuckDuckGo HTTP bodies (BL-022)
- SSE transport migration (P15)
- `ui/` frontend bundle performance
- SQL agent path / `parameter_builders.py`
- Production load testing / benchmarking
- Re-running performance or code-health audits (source artifacts are final)

## Verdict

**ready with deferrals**

All **Critical** and most **High** audit items are either **resolved in subsequent 2026-07-21 increments** or have concrete actions (RF01, RF07, RF08). Five actionable items (RF01–RF05) are **safe to implement now** without product decisions. RF08 and RF10 remain explicitly deferred with documented rationale. No layer-boundary violations proposed.
