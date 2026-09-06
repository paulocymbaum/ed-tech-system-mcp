# Engineering Backlog

**Date:** 2026-07-21  
**Sources:** [CODE_HEALTH_AUDIT1.md](../changelog/2026-07-21/code-health/CODE_HEALTH_AUDIT1.md) · [PERFORMANCE_AUDIT1.md](../changelog/2026-07-21/performance/PERFORMANCE_AUDIT1.md) · [RICE.md](RICE.md)

Tasks are ordered by RICE priority. Each task lists **source audit IDs** for traceability. Check off when done.

**Status key:** `open` · `in_progress` · `done` · `deferred` · `wont_do`  
**Tag key (done tasks):** `done-YYYY-MM-DD` — completion date stamp (set when all checklist items are checked)

---

## P0 — Ship blockers (before MCP tools go to production)

### BL-001 — Integrate orchestration paths {#bl-001}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H04 · D01 · A01 · P09  
**Layer:** application  
**Effort:** medium (1.0 d)

- [x] Refactor LangGraph nodes to delegate to `DocumentVideoWorkflow.retrieve_with_videos()` (or inject shared ports)
- [x] Remove skeleton count-only nodes (`_count_documents`, `_count_videos`) once real I/O is wired
- [x] Ensure graph state reflects workflow outputs (document/video counts or result refs)
- [x] Update `tests/test_workflows.py` and `tests/test_llm.py` for integrated path
- [x] Verify local UI graph view still renders after node consolidation

---

### BL-002 — Wire composition root to entrypoint {#bl-002}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H02 · H09 · P02  
**Layer:** entrypoint · interface · infrastructure  
**Effort:** medium (1.0 d)

- [x] Call `build_document_video_workflow(settings)` from `main()` or tool-registration path
- [x] Call `build_mcp_tool_cache(settings)` and expose cache helper to `custom_tools.py`
- [x] Wrap MCP tool handlers with `McpToolInteractionCache.get_or_invoke(tool_name, args, invoker)`
- [x] Add integration test proving tool cache hit on identical args
- [x] Annotate deferred factories in `wiring.py` until complete (if partial)

---

### BL-003 — Share single cache store at composition root {#bl-003}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** R03 · P11  
**Layer:** entrypoint · wiring  
**Effort:** small (0.5 d)

- [x] Create one `ICacheStore` instance in `main()` (or `ApplicationContext`)
- [x] Pass shared store into `build_document_video_workflow`, `build_mcp_tool_cache`, `build_chat_model`
- [x] Add test asserting single `create_cache_store` call per process boot when cache enabled

---

### BL-010 — Parallelize independent workflow I/O {#bl-010}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P01  
**Layer:** application  
**Effort:** small (0.5 d)

- [x] Use `asyncio.gather` when title fallback is not required (empty docs → query-only path)
- [x] Keep sequential Supabase → YouTube order when first-document title is needed
- [x] Add test for parallel vs sequential branch selection
- [x] Document latency trade-off in workflow docstring

---

### BL-011 — Enforce workflow timeout and retry policy {#bl-011}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H05 · P04 · P13 · A02  
**Layer:** application · interface  
**Effort:** small (0.5 d)

- [x] Wire `ainvoke_with_workflow_timeout()` for all graph invocations (MCP `run_workflow`, local UI)
- [x] Add typed `DocumentVideoState` alias to replace `Any` on timeout helper
- [x] Review `node_retries=3` → `max_attempts=4` impact on read-only external calls
- [x] Add test for workflow timeout enforcement (`asyncio.wait_for` path)
- [x] Consider lower retry count on idempotent read nodes after profiling

---

### BL-012 — Production cache enablement {#bl-012}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P03  
**Layer:** entrypoint · docs  
**Effort:** trivial (0.25 d)

- [x] Document `CACHE_ENABLED=true` + Redis as production requirement in `ENVIRONMENT_SETUP.md`
- [x] Add deployment checklist entry (Doppler / `.env.example`)
- [x] Verify graceful degradation path still works when Redis is down

---

### BL-013 — Prune MCP response payloads {#bl-013}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P08  
**Layer:** interface · domain  
**Effort:** small (0.5 d)

- [x] Add interface-layer response DTO (e.g. `DocumentSummary`: `id`, `title`, snippet)
- [x] Map `DocumentHit` → summary at MCP tool boundary; omit full `content` from JSON-RPC
- [x] Add validation test for pruned response schema

---

## P1 — High value (next sprint)

### BL-004 — Lazy-init LLM at startup {#bl-004}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P05  
**Layer:** entrypoint · wiring  
**Effort:** small (0.5 d)

- [x] Defer `build_chat_model()` until first `get_chat_model()` consumer or agent invocation
- [x] Keep `initialize_application_runtime(operational)` for workflow config only on boot
- [x] Add test: `main()` boot without Groq key when no LLM path invoked
- [x] Measure cold-start improvement (informal note in changelog)

---

### BL-005 — Wire web search client {#bl-005}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H01  
**Layer:** application · wiring  
**Effort:** small (0.5 d)

- [x] Decide: wire `build_search_client()` into agent node or document workflow
- [x] If deferred: add `# deferred — web search` comment at `build_search_client` in `wiring.py`
- [x] Update `AGENTIC_ARCHITECTURE.md` with chosen path

---

### BL-006 — Implement MCP tools beyond health_check {#bl-006}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H08 · A04  
**Layer:** interface  
**Effort:** small (0.5 d)

- [x] Implement `search_youtube` using `VideoSearchRequest` / `VideoSearchResponse`
- [x] Implement `find_documents` (or document+video composite tool per architecture)
- [x] Remove "Tool implementations deferred" placeholder docstring from `custom_tools.py`
- [x] Register tools in `custom_tools.py`; link to changelog increment
- [x] Add behavior tests in `tests/test_interface_tools.py`

---

### BL-007 — Bootstrap logging from LOG_LEVEL {#bl-007}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H06 · O04  
**Layer:** entrypoint  
**Effort:** small (0.5 d)

- [x] Configure `logging.basicConfig(level=settings.log_level)` in `main.py` bootstrap
- [x] Map `LOG_LEVEL` string to `logging` level (INFO, DEBUG, etc.)
- [x] Add entrypoint test asserting log level is applied
- [x] Remove or update env docs if field is removed instead

---

### BL-008 — Typed MCP tool cache envelope {#bl-008}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** A05  
**Layer:** infrastructure  
**Effort:** small (0.5 d)

- [x] Replace `json.dumps(..., default=str)` with Pydantic serialization envelope
- [x] Remove `# type: ignore` on cache deserialize path
- [x] Add round-trip test for complex tool result types

---

### BL-009 — Activate domain exception taxonomy {#bl-009}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H07  
**Layer:** domain · infrastructure · application  
**Effort:** small (0.5 d)

- [x] Raise `ResourceNotFoundError` from adapters on empty/missing resources
- [x] Raise domain `ValidationError` (rename if Pydantic collision) on invariant violations
- [x] Map domain exceptions to MCP error responses at interface boundary
- [x] Extend `tests/test_domain_exceptions.py` with raise/catch paths

---

### BL-014 — Tune timeouts after adapter profiling {#bl-014}

**Status:** deferred  
**Source IDs:** P14 · P19  
**Layer:** entrypoint · infrastructure  
**Effort:** trivial (0.25 d)

- [ ] Profile Supabase, YouTube, Groq P99 latencies once adapters are implemented
- [ ] Align `agent_node_timeout` in `config.json` with measured port sum + retry budget
- [ ] Set explicit `timeout=` on `ChatGroq` in `groq_adapter.py`
- [ ] Document expected P99 per port in `ENVIRONMENT_SETUP.md`

---

### BL-015 — Optimize cache serialization {#bl-015}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P07  
**Layer:** infrastructure  
**Effort:** small (0.5 d)

- [x] Prune large fields before `model_dump()` in `cached_adapters.py`
- [x] Evaluate compression for large document lists in Redis
- [x] Cap maximum cached payload size with fallback to uncached path

---

### BL-017 — Port-call timing spans {#bl-017}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** O01  
**Layer:** infrastructure · application  
**Effort:** medium (1.0 d)

- [x] Add structured log spans around `find_documents`, `search_videos`, `search` port calls
- [x] Include duration_ms, operation name, and cache hit/miss flag
- [x] Ensure spans respect `LOG_LEVEL` (debug vs info)

---

### BL-018 — Cache hit/miss metrics {#bl-018}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** O02  
**Layer:** infrastructure  
**Effort:** small (0.5 d)

- [x] Log cache hit/miss at debug level in `cached_adapters.py` and `cached_llm.py`
- [x] Optional: expose counters for future metrics backend
- [x] Add test asserting hit log on second identical call

---

### BL-019 — Per-tool latency breakdown {#bl-019}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** O03  
**Layer:** interface  
**Effort:** small (0.5 d)

- [x] Wrap MCP tool handlers with timing decorator or middleware
- [x] Log tool name, duration_ms, and outcome at INFO when `LOG_LEVEL=INFO`
- [x] Add test for timing wrapper invocation

---

## P2 — Medium (before production hardening)

### BL-016 — Cache-aside stampede protection {#bl-016}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P06  
**Layer:** infrastructure  
**Effort:** medium (1.0 d)

- [x] Add per-key `asyncio.Lock` or singleflight wrapper in cache-aside helper
- [x] Apply to `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient`
- [x] Add concurrent-request test: N parallel misses → 1 inner call

---

### BL-020 — Distributed trace IDs across workflow nodes {#bl-020}

**Status:** deferred  
**Source IDs:** O05  
**Layer:** application  
**Effort:** medium (1.0 d)

- [ ] Generate `trace_id` at workflow entry; propagate through graph state
- [ ] Include `trace_id` in port-call log spans (depends on BL-017)
- [ ] Document trace format for local debugging

---

### BL-021 — Alert on retry exhaustion and timeouts {#bl-021}

**Status:** deferred  
**Source IDs:** O06  
**Layer:** application · entrypoint  
**Effort:** small (0.5 d)

- [ ] Log ERROR on retry policy exhaustion and `asyncio.TimeoutError` from workflow timeout
- [ ] Define alert thresholds for production monitoring (document only until metrics exist)

---

### BL-022 — Implement infrastructure adapters with HTTP timeouts {#bl-022}

**Status:** deferred  
**Source IDs:** A03 · PC01  
**Layer:** infrastructure  
**Effort:** large (2.0 d)

- [ ] Implement `SupabaseRepository.find_documents` with pagination and row cap
- [ ] Implement `YouTubeDataApiClient.search_videos` with quota-aware field masks
- [x] ~~Implement `DuckDuckGoSearchClient.search`~~ — **cancelled 2026-09-06**; Tavily is required, stub removed
- [ ] Require `httpx` `timeout=` on all external HTTP calls
- [ ] Gate MCP tools until adapters pass homologation tests
- [ ] Re-run performance audit after implementation

---

### BL-023 — Memoize local UI workflow graph {#bl-023}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P10  
**Layer:** interface  
**Effort:** trivial (0.25 d)

- [x] Cache `list_registered_workflows()` result at module level
- [x] Avoid `build_document_video_graph()` on every `/api/workflows` request
- [x] Add test or manual check for UI list endpoint

---

### BL-024 — Document async-only LLM cache contract {#bl-024}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** P12  
**Layer:** infrastructure · docs  
**Effort:** trivial (0.25 d)

- [x] Document that `CachedChatModel` only caches `_agenerate` (async path)
- [x] Add note in `AGENTIC_ARCHITECTURE.md` or adapter docstring
- [x] Defer sync cache path unless sync callers are introduced

---

### BL-025 — Resolve external_apis.py placeholder {#bl-025}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** H03  
**Layer:** infrastructure  
**Effort:** trivial (0.25 d)

- [x] Delete `external_apis.py` if no near-term third-party adapter planned, **or**
- [x] Add first adapter and export from `infrastructure/__init__.py`

---

### BL-026 — Remove empty TYPE_CHECKING block {#bl-026}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** R04  
**Layer:** infrastructure  
**Effort:** trivial (0.25 d)

- [x] Remove `if TYPE_CHECKING: pass` from `cache_config.py` lines 14–15
- [x] Run `uv run ruff check` and `uv run mypy src/`

---

### BL-027 — Single source of truth for config defaults {#bl-027}

**Status:** done  
**Tag:** done-2026-07-21  
**Source IDs:** D04  
**Layer:** application · entrypoint  
**Effort:** small (0.5 d)

- [x] Load `DEFAULT_WORKFLOW_EXECUTION_CONFIG` from `config.json` at import or startup
- [x] Remove hardcoded duplicate defaults in `workflow_config.py`
- [x] Add test: Python fallback matches committed `config.json`

---

### BL-028 — Shared HTTP client base for adapters {#bl-028}

**Status:** deferred  
**Source IDs:** D02  
**Layer:** infrastructure  
**Effort:** small (0.5 d)

- [ ] Extract shared timeout/retry/header setup when ≥2 adapters share HTTP logic
- [ ] Depends on BL-022 adapter implementation

---

## Accepted / no action

| Source ID | Decision | Rationale |
| :--- | :--- | :--- |
| R01 | **wont_do** | `create_agent()` facade is intentional per `AGENTIC_ARCHITECTURE.md` |
| R02 | **wont_do** | `create_mcp_server()` singleton is extension point for tool registration |
| D03 | **deferred** | Extract `_cache_aside()` only when a fourth variant appears |
| P15 | **wont_do** | Stdio transport acceptable at current scale |
| P16 | **wont_do** | `reload=True` is dev-only in `local_ui_main.py` |
| P17 | **wont_do** | Stable cache keys — positive pattern, no change |
| P18 | **wont_do** | Bounded port defaults — positive pattern, keep |

---

## Summary

| Tier | Tasks | Open | Deferred | Done |
| :--- | :---: | :---: | :---: | :---: |
| P0 | 8 | 0 | 0 | 8 |
| P1 | 11 | 0 | 2 | 10 |
| P2 | 9 | 0 | 4 | 6 |
| **Total actionable** | **28** | **0** | **6** | **23** |

**Recommended execution order:** BL-001 → BL-003 → BL-002 → BL-010 → BL-011 → BL-012 → BL-006 → BL-013 → BL-004 → BL-022 (when adapters are in scope).
