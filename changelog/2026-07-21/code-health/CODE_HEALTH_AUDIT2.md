# Code Health Audit 2: Full-system maintainability scan (post-implementation)

**Date:** 2026-07-21
**Scope:** code-health (cross-cutting)
**Status:** final
**References:** [CODE_HEALTH_AUDIT1](./CODE_HEALTH_AUDIT1.md) (stale), [REFACTOR1](../refactor/REFACTOR1.md), [application/CODE_REVIEW2](../application/CODE_REVIEW2.md), [entrypoint/CODE_REVIEW4](../entrypoint/CODE_REVIEW4.md), `AGENTIC_ARCHITECTURE.md`

## Executive summary

Same-day implementation work materially improved maintainability: MCP tools are wired, the composition root initializes a shared `ApplicationContext`, LangGraph nodes delegate to `DocumentVideoWorkflow`, and `external_apis.py` is gone. The codebase remains **lint-clean** (44 `src/` modules, 143 collected tests). Remaining debt clusters in three areas: **(1)** the local UI entrypoint still skips composition-root bootstrap, **(2)** intentionally deferred web-search and HTTP adapter bodies leave MCP tools that call `NotImplementedError` stubs at runtime, and **(3)** duplicated workflow-response assembly and parallel cache-aside implementations without the shared `run_cache_aside` singleflight helper on MCP-tool and LLM paths.

## Delta from CODE_HEALTH_AUDIT1 (resolved — do not re-open)

| AUDIT1 ID | Was | Now |
| :--- | :--- | :--- |
| H02 | `build_document_video_workflow` / `build_mcp_tool_cache` unwired | `initialize_application_runtime()` wires both; `main.py` calls it |
| H03 | `external_apis.py` dead module | **Deleted** — no file under `src/` |
| H04, D01, A01 | Skeleton graph vs workflow class | Graph nodes call `DocumentVideoWorkflow` via `get_document_video_workflow()` |
| H05 | `ainvoke_with_workflow_timeout` unused | Wired from `run_document_video_graph()` |
| H06 | `log_level` stale | `configure_logging()` in `main.py` reads `settings.log_level` |
| H08 | Validation schemas unused | `search_youtube`, `find_documents`, `run_workflow` use `validation.py` |
| H09 | MCP tool cache unwired | `set_mcp_tool_cache()` in `initialize_application_runtime()` |
| R03 | Multiple `create_cache_store()` per boot | Single `cache_store` in `ApplicationContext` |
| D03 | Repeated cache-aside in adapters | Extracted `run_cache_aside()` + `CacheAsideCoordinator` |
| D04 | Config defaults duplicated | `DEFAULT_WORKFLOW_EXECUTION_CONFIG` loads `config.json` |
| R04 | Empty `TYPE_CHECKING` in `cache_config.py` | Removed |
| A02 | `Any` on timeout helper | Typed `DocumentVideoGraph` / `DocumentVideoState` |
| A05 | `json.dumps(default=str)` in MCP cache | `McpToolCacheEnvelope.pack/unpack` |

## Import baseline

| Entry point | Modules reachable | Notes |
| :--- | :--- | :--- |
| `main.py` | `settings`, `operational_config`, `wiring`, `interface/mcp_server`, `interface/custom_tools` (registers 4 MCP tools), transitive: `application/{agent,workflows,workflow_*,llm,mcp_tool_cache_runtime}`, `domain/*`, `infrastructure/{supabase,search,youtube,cached_*,mcp_tool_cache,redis,groq,cache_*}` | Full composition root; `build_search_client()` defined in `wiring.py` but **never called** |
| `local_ui_main.py` | `interface/local_ui/api` → `application/{agent,workflow_graph}`, `interface/validation` | **Does not** call `bootstrap_environment()`, `load_settings()`, or `initialize_application_runtime()` |
| `wiring.py` | All adapter builders, `DocumentVideoWorkflow`, `McpToolInteractionCache`, lazy LLM registration | `initialize_application_runtime(operational, settings)` is the single production wiring path |

**Reachability-sensitive paths traced:**

- MCP tools → `_cached_tool_invoke` → `get_document_video_workflow()` / `run_document_video_graph()` → ports
- LangGraph nodes → `_require_workflow()` → `DocumentVideoWorkflow` methods → ports
- Local UI POST run → `run_document_video_graph()` (fails without wiring bootstrap)
- `get_chat_model()` — registered lazy builder in `wiring.py`; **zero `src/` callers** (tests only)

**No orphan `src/` modules:** all 44 files under `src/mcp_server/` are import-reachable from `main.py` and/or `local_ui_main.py`.

## Areas reviewed

| Area | Paths | Primary concern |
| :--- | :--- | :--- |
| Entrypoint | `main.py`, `local_ui_main.py`, `wiring.py`, `settings.py` | Local UI missing runtime bootstrap; deferred `build_search_client` |
| Interface | `custom_tools.py`, `local_ui/api.py`, `validation.py`, `error_mapping.py` | Duplicated workflow response mapping; `RuntimeError` on missing workflow |
| Application | `agent.py`, `workflows.py`, `llm.py` | Per-invocation graph recompilation; LLM accessor unused in production |
| Domain | `exceptions.py`, `invariants.py`, `interfaces.py` | Invariants active; adapter bodies still stub |
| Infrastructure | `*_client.py`, `cached_*.py`, `mcp_tool_cache.py` | `NotImplementedError` stubs; MCP/LLM cache paths lack singleflight |
| Tests | `tests/` (143 collected) | No import errors; local UI run endpoint untested post-bootstrap |

## Findings by category

### Dead code

| ID | Pattern | Location | Evidence | Impact | Recommendation | Removal risk | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| H01 | dead-entry-unused-builder | `wiring.py:build_search_client` | Factory + tests (`test_c13`–`c14`, `c27`, `c34`); zero production callers; docstring marks `# deferred — web search` per BL-005/BL-022 | Web-search port scaffolded but not injectable at runtime; `CachedSearchClient` never wraps a live client in production | Wire when `langchain_tools.search_web` and MCP `search_web` ship; deferral already documented in `AGENTIC_ARCHITECTURE.md` | verify callers | medium |
| H02 | dup-entry-dual-bootstrap | `local_ui_main.py:main` | Starts uvicorn only; never calls `initialize_application_runtime()`. `run_document_video_graph()` → `_require_workflow()` raises `RuntimeError("Document video workflow has not been initialized")` when POST run is used | Local workflow UI cannot execute graphs with real ports; diverges from `main.py` bootstrap | Mirror `main.py` sequence: `bootstrap_environment()` → `load_settings()` → `configure_logging()` → `load_operational_config()` → `initialize_application_runtime()` before `uvicorn.run` (REFACTOR1 RF01) | verify callers | small |
| H03 | dead-app-unused-node (latent) | `application/llm.py:get_chat_model` | Lazy builder registered in `wiring.py`; `rg get_chat_model src/` → definition only (no agent node or tool consumer) | LLM stack (Groq + `CachedChatModel`) wired but idle; future LLM nodes may assume accessor is already exercised | Keep until SQL/LLM agent nodes land; add integration test when first node calls `get_chat_model()` | needs product decision | small |
| H04 | dead-inf-stub-on-hot-path | `infrastructure/{supabase_client,search_client,youtube_client}.py` | After invariant guards, each adapter raises `NotImplementedError` (BL-022). MCP `find_documents` / `search_youtube` / `run_workflow` reach these bodies when fakes are not injected | Production MCP calls with valid credentials fail at runtime with `NotImplementedError`, not domain-mapped MCP errors | Implement adapter bodies (BL-022) or gate MCP tools until adapters ship | needs product decision | large |

### Duplicated code

| ID | Pattern | Location(s) | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| D01 | dup-ifc-tool-boilerplate | `interface/custom_tools.py:_invoke_run_workflow` vs `interface/local_ui/api.py:run_workflow` | Both call `run_document_video_graph()`, extract `documents`/`videos` from state, build identical `WorkflowRunResponse(...)` (~8 lines each) | Response-shape changes require two edits; local UI and MCP can drift | Extract `workflow_state_to_run_response(state: DocumentVideoState) -> WorkflowRunResponse` in `validation.py` or a thin interface helper | small |
| D02 | dup-inf-cache-wrap | `infrastructure/mcp_tool_cache.py`, `infrastructure/cached_llm.py` vs `infrastructure/cache_aside.py` | Port adapters use `run_cache_aside()` with `CacheAsideCoordinator` singleflight; MCP tool and LLM caches hand-roll get/miss/set without singleflight | Cache stampede possible on MCP-tool and LLM hot keys under concurrent load (REFACTOR1 RF02) | Route MCP-tool and LLM miss paths through `run_cache_aside()` or shared coordinator | small |
| D03 | ai-dual-implementation | `application/workflows.py:retrieve_with_videos` vs `application/agent.py` graph path | `find_documents` MCP tool uses parallel I/O + title fallback; `run_workflow` / graph uses sequential nodes — documented in `AGENTIC_ARCHITECTURE.md` § Capability flows | Intentional latency/observability trade-off, not accidental copy-paste | Document in module docstrings only; no merge unless product drops one path | trivial |

### Redundant code

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| R01 | red-app-thin-wrapper | `application/agent.py:create_agent` | `return build_document_video_graph()` — single-line delegate | Noise unless facade is part of stable public API | Keep per `AGENTIC_ARCHITECTURE.md` growth path | trivial |
| R02 | red-entry-pass-through | `interface/mcp_server.py:create_mcp_server` | Returns module-level `mcp` singleton unchanged | Minimal; extension point for future multi-server config | Keep | trivial |
| R03 | red-wrapper-chain | `application/agent.py:run_document_video_graph` | Calls `create_agent()` → `build_document_video_graph()` → `compile()` on **every** invocation; `list_registered_workflows()` separately memoizes another compiled graph in `_REGISTERED_WORKFLOWS` | Redundant graph compilation per MCP `run_workflow` / UI run; two compiled instances for same definition | Memoize compiled graph at module level (shared by `run_document_video_graph` and registry) | small |
| R04 | red-wrapper-chain | `wiring.py:build_document_video_workflow`, `build_mcp_tool_cache` | When `cache_enabled=false`, `cache is None` falls back to `create_cache_store(settings)` (NoOp) even though `initialize_application_runtime` always passes explicit store | Harmless extra NoOp allocation on misdirected direct builder calls | Tighten builders to require explicit store when called outside tests, or document test-only fallback | trivial |

### AI code smells

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| A01 | ai-ifc-generic-handler | `interface/custom_tools.py:_invoke_search_youtube`, `_invoke_find_documents` | `RuntimeError` when `get_document_video_workflow()` is `None`; not mapped via `raise_as_mcp_error` (unlike `DomainError` in `_cached_tool_invoke`) | Misconfiguration surfaces as generic 500-style tool failure instead of typed MCP error | Raise `ResourceNotFoundError` or dedicated config error mapped in `error_mapping.py` | small |
| A02 | ai-todo-ship | `infrastructure/*_client.py` | `raise NotImplementedError(...)` after validation guards in all three external adapters | Scaffold shipped on paths exposed by four MCP tools | Track BL-022; consider feature flag or startup guard when adapters remain stubs | small |
| A03 | ai-app-any-escape | `application/workflow_graph.py:RegisteredWorkflow.graph` | `CompiledStateGraph[Any, Any, Any]` for UI introspection only | Weak typing on non-hot path | Acceptable for UI DTO; tighten when graph registry grows | trivial |
| A04 | ai-over-factory | `wiring.py` + `application/llm.py` | Lazy LLM factory + `CachedChatModel` wrapper with no production consumer | Composition complexity without runtime benefit until agent LLM nodes ship | Defer removal; wire first LLM node in same PR that adds consumer | small |

## Severity rollup

### Critical

None. No silent data-loss paths; Redis degradation logs warnings and returns cache miss. Domain invariant violations map to typed MCP errors via `error_mapping.py`.

### High

- **H02** — Local UI entrypoint missing composition-root bootstrap (workflow runs fail)
- **H04** — MCP tools expose adapter stubs that raise `NotImplementedError` at runtime (BL-022 blocker for real usage)

### Medium

- **H01** — `build_search_client` unwired (documented deferral; blocks web search)
- **H03** — `get_chat_model()` has no production consumer (idle LLM stack)
- **D01** — Duplicated `WorkflowRunResponse` assembly (MCP + local UI)
- **D02** — MCP-tool / LLM cache paths lack singleflight used by port adapters
- **R03** — Graph recompiled on every `run_workflow` invocation
- **A01** — `RuntimeError` for uninitialized workflow bypasses domain error mapping
- **A02** — `NotImplementedError` stubs on MCP-exposed paths

### Low

- **D03** — Intentional dual orchestration paths (parallel vs sequential)
- **R01**, **R02**, **R04** — Thin facades and benign builder fallbacks
- **A03**, **A04** — Minor typing / idle-factory smells on deferred features

## Positive patterns observed

- Clean Architecture boundaries preserved: interface tools delegate to application; no infrastructure imports in application/domain
- Single shared `ICacheStore` per process in `ApplicationContext` (AUDIT1 R03 resolved)
- Graph nodes delegate to `DocumentVideoWorkflow` — one orchestration implementation for port calls (AUDIT1 D01 resolved)
- `run_cache_aside()` + `CacheAsideCoordinator` centralize port-adapter cache-aside with stampede protection
- Domain invariants (`require_non_empty_text`, `require_credential`) raise typed `DomainValidationError` / `ResourceNotFoundError`; mapped at MCP boundary
- `McpToolCacheEnvelope` replaces unsafe `json.dumps(default=str)` for tool result caching
- `configure_logging()` consumes `LOG_LEVEL`; operational timeouts load from committed `config.json`
- `ruff check src/ tests/` — all passed; `mypy src/` — 44 files, no issues
- Tests favor behavioral fakes (`FakeRepository`, `InMemoryCacheStore`) over mock-only theatre
- No `utils.py` / `helpers.py` dumping grounds; no broad `except Exception: pass` in business logic

## Verification performed

- [x] Import graph from entrypoints (`main.py`, `local_ui_main.py`, `wiring.py`)
- [x] `uv run ruff check src/ tests/` — all passed
- [x] `uv run mypy src/` — success (44 source files)
- [x] Changelog cross-check (AUDIT1, REFACTOR1, application/entrypoint CODE_REVIEW2–4)
- [x] `uv run pytest --collect-only` — 143 tests collected, no import errors

## Recommended remediation order

1. **Bootstrap local UI (H02)** — Align `local_ui_main.py` with `main.py` wiring; add POST run test with fakes.
2. **Implement or gate adapter bodies (H04, A02)** — BL-022: replace `NotImplementedError` before production MCP usage.
3. **Consolidate workflow response mapping (D01)** — Single helper for `WorkflowRunResponse` from graph state.
4. **Memoize compiled graph (R03)** — Share one compiled graph between `run_document_video_graph` and workflow registry.
5. **Extend singleflight to MCP/LLM caches (D02)** — Reuse `run_cache_aside` per REFACTOR1 RF02.
6. **Map misconfiguration errors (A01)** — Replace `RuntimeError` with domain errors at workflow accessor sites.
7. **Wire web search when ready (H01)** — `build_search_client` → `langchain_tools` → MCP `search_web`.
8. **First LLM consumer (H03, A04)** — Agent node that calls `get_chat_model()` with integration test.

## Out of scope / deferred

- Implementing DuckDuckGo / Supabase / YouTube HTTP bodies (BL-022 — intentional stubs)
- `application/langchain_tools.py`, `parameter_builders.py`, SQL agent path (planned in `AGENTIC_ARCHITECTURE.md`)
- `ui/` frontend bundle
- Performance tuning (see `PERFORMANCE_AUDIT1.md`; several items resolved same day)
- Documentation drift between `ARCHITECTURE.md` tree and on-disk layout (docs issue, not code defect)

## Verdict

**acceptable with known debt**

The same-day implementation pass closed most AUDIT1 High findings (wiring, graph delegation, MCP tools, logging, cache consolidation). Remaining risk is **concentrated and actionable**: local UI bootstrap gap (H02), runtime stub adapters on live MCP tools (H04), and minor duplication on workflow responses and cache helpers. None block CI or lint gates; all block **production-ready** document/video discovery until BL-022 lands and the local UI entrypoint is aligned with `main.py`.
