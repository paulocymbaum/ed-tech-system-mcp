# Code Health Audit 1: Full-system maintainability scan

**Date:** 2026-07-21
**Scope:** code-health (cross-cutting)
**Status:** final
**References:** [application/CODE_REVIEW1.md](../application/CODE_REVIEW1.md), [infrastructure/CODE_REVIEW1.md](../infrastructure/CODE_REVIEW1.md), [entrypoint/CODE_REVIEW2.md](../entrypoint/CODE_REVIEW2.md), `AGENTIC_ARCHITECTURE.md`

## Executive summary

The codebase is a **well-structured early scaffold** with clean layer boundaries, zero `ruff`/`mypy` violations, and 82 collected tests. The dominant maintainability theme is **parallel unintegrated paths**: composition-root factories (`build_document_video_workflow`, `build_search_client`, `build_mcp_tool_cache`) and application orchestration (`DocumentVideoWorkflow`, `VideoSearchRequest`) exist but are not wired to production entrypoints, while the LangGraph agent runs a separate skeleton graph that does not call ports or the workflow class. Secondary themes are **placeholder modules** (`external_apis.py`, domain exceptions) and **stale settings** (`log_level`) with no consumers.

## Import baseline

| Entry point | Modules reachable | Notes |
| :--- | :--- | :--- |
| `main.py` | `settings`, `operational_config`, `wiring`, `interface/mcp_server`, `interface/custom_tools`, all `wiring` transitive deps (`application/llm`, `workflow_config`, `workflows`, `domain/*`, `infrastructure/*` except `external_apis.py`) | Does **not** import `agent.py`, `validation.py`, or `domain/exceptions.py` |
| `local_ui_main.py` | `interface/local_ui/api` → `application/agent`, `application/workflow_graph` | No `bootstrap_environment()`, `load_settings()`, or `initialize_application_runtime()` |
| `wiring.py` | Composition root for all adapters and `DocumentVideoWorkflow` class import | `build_document_video_workflow()` / `build_mcp_tool_cache()` / `build_search_client()` are defined but not called from entrypoints |

**Unreachable from any production entrypoint (candidates):**

- `infrastructure/external_apis.py` — empty placeholder, zero importers
- `interface/validation.py` — test/smoke imports only
- `domain/exceptions.py` — test/smoke imports only; never raised in `src/`

## Areas reviewed

| Area | Paths | Primary concern |
| :--- | :--- | :--- |
| Entrypoint | `main.py`, `local_ui_main.py`, `wiring.py`, `settings.py`, `operational_config.py` | Unwired composition factories; stale `log_level` |
| Interface | `custom_tools.py`, `mcp_server.py`, `validation.py`, `local_ui/` | Schema/tools exist only as stubs; single `health_check` tool |
| Application | `workflows.py`, `agent.py`, `llm.py`, `workflow_config.py`, `workflow_graph.py` | Dual orchestration paths (workflow class vs skeleton graph) |
| Domain | `interfaces.py`, `schemas.py`, `exceptions.py`, `cache.py` | Unused exception taxonomy |
| Infrastructure | `*_client.py`, `cached_adapters.py`, `mcp_tool_cache.py`, `external_apis.py` | Adapter stubs; unwired search/MCP-tool cache paths |
| Tests | `tests/` | Good coverage of contracts; some symbols tested but not production-wired |

## Findings by category

### Dead code

| ID | Pattern | Location | Evidence | Impact | Recommendation | Removal risk | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| H01 | dead-entry-unused-builder | `wiring.py:build_search_client` | Defined and tested (`tests/test_cache.py`); zero production callers; `DocumentVideoWorkflow` does not inject `ISearchClient` | Web-search port fully scaffolded but permanently sidelined unless explicitly wired | Wire into a workflow/agent node when web search ships, or document as deferred and add a `# deferred` comment at factory | verify callers | small |
| H02 | dead-entry-unused-builder | `wiring.py:build_document_video_workflow`, `build_mcp_tool_cache` | Factories exist; `main.py` only calls `initialize_application_runtime()`; noted in [infrastructure/CODE_REVIEW1.md](../infrastructure/CODE_REVIEW1.md) L105 | Composition root advertises paths that production never uses; reviewers assume workflows run at startup | Call from `main()` or interface tool registration when MCP tools land; until then annotate as deferred in `wiring.py` | verify callers | small |
| H03 | dead-module | `infrastructure/external_apis.py` | File contains only a docstring placeholder; `rg` shows no imports | Noise in infrastructure layer; false signal of additional integrations | Delete when no near-term third-party adapter is planned, or add `__all__` export when first adapter lands | safe to delete | trivial |
| H04 | dead-app-unused-workflow | `application/workflows.py:DocumentVideoWorkflow` | Class imported in `wiring.py` but `build_document_video_workflow()` never called from entrypoints; only exercised in `tests/test_workflows.py` and `tests/test_cache.py` | Real orchestration logic (port calls, title fallback) isolated from LangGraph path | Integrate graph nodes to delegate to `DocumentVideoWorkflow` or inject ports into nodes | needs product decision | medium |
| H05 | dead-symbol | `application/agent.py:ainvoke_with_workflow_timeout` | Defined once; no callers in `src/` or `tests/` | Dead helper adds API surface without tests | Wire when MCP `run_workflow` tool ships, or remove until needed | safe to delete | trivial |
| H06 | dead-entry-stale-config | `settings.py:log_level` | Field defined with `LOG_LEVEL` alias; no reader in `src/mcp_server/` (`rg log_level` hits docs only) | Misleading env contract; operators set a knob with no effect | Add logging bootstrap in `main.py` or remove field until logging is implemented | needs product decision | small |
| H07 | dead-dom-unused-exception | `domain/exceptions.py` | `ResourceNotFoundError`, `ValidationError`, `DomainError` never raised in production code (`rg "raise (DomainError|ResourceNotFoundError|ValidationError)"` → no matches) | False error taxonomy; Pydantic `ValidationError` name collision risk at interface layer | Raise from adapters/workflows when implemented, or trim to base `DomainError` only until used | verify callers | small |
| H08 | dead-ifc-unused-schema | `interface/validation.py:VideoSearchRequest`, `VideoSearchResponse` | Only imported by `tests/test_validation.py` and `tests/test_smoke.py`; no MCP tool uses them | Schema drift from future `search_youtube` tool documented in `AGENTIC_ARCHITECTURE.md` | Keep until tool implementation; wire in same PR as `search_youtube` | needs product decision | small |
| H09 | dead-inf-unused-adapter | `infrastructure/mcp_tool_cache.py` (production path) | `McpToolInteractionCache` built by `build_mcp_tool_cache()` but factory unwired; only tests exercise it | Dead integration path; type-unsafe `json.dumps(..., default=str)` noted in CODE_REVIEW1 | Wire when MCP tools beyond `health_check` land | verify callers | medium |

### Duplicated code

| ID | Pattern | Location(s) | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| D01 | dup-app-workflow-logic | `application/workflows.py` vs `application/agent.py` | `DocumentVideoWorkflow.retrieve_with_videos()` calls `IDataRepository` + `IVideoSearchClient` with title fallback; graph nodes `_count_documents` / `_count_videos` return hardcoded `0` and never touch ports | Two orchestration stories for the same use case; bug fixes in workflow won't reach agent/graph path | Refactor nodes to call `DocumentVideoWorkflow` or shared port-injection functions | medium |
| D02 | dup-symmetric-adapters | `infrastructure/supabase_client.py`, `search_client.py`, `youtube_client.py` | All three adapters are single-method stubs raising `NotImplementedError` with identical structure | Acceptable scaffold symmetry; will become duplication once HTTP logic is added | Extract shared HTTP client base only when ≥2 adapters share timeout/retry blocks | small |
| D03 | dup-inf-cache-wrap | `infrastructure/cached_adapters.py` | `CachedDataRepository`, `CachedSearchClient`, `CachedVideoSearchClient` repeat the same cache-aside sequence (rule check → key → get → invoke → set) | Fix-once-fix-many burden when cache semantics change | Consider a generic `_cache_aside()` helper **only if** a third identical variant appears; current symmetry is intentional per infrastructure review | small |
| D04 | dup-config-defaults | `application/workflow_config.py` vs `config.json` | `DEFAULT_WORKFLOW_EXECUTION_CONFIG` hardcodes `node_retries=3`, `workflow_timeout_seconds=300`, `agent_node_timeout_seconds=60` matching `config.json` defaults | Drift risk if `config.json` changes without updating Python fallback | Load defaults from `config.json` or generate one from the other | small |

### Redundant code

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| R01 | red-app-thin-wrapper | `application/agent.py:create_agent` | `return build_document_video_graph()` — single-line delegate | Extra indirection; documented as stable facade in `AGENTIC_ARCHITECTURE.md` | Keep as facade per architecture doc; acceptable | trivial |
| R02 | red-entry-pass-through | `interface/mcp_server.py:create_mcp_server` | Returns module-level `mcp` singleton with no configuration | Minimal noise; provides extension point for future tool registration | Keep until multiple server instances needed | trivial |
| R03 | red-wrapper-chain | `wiring.py:build_document_video_workflow`, `build_mcp_tool_cache`, `build_chat_model` | Each calls `create_cache_store()` independently; noted in CODE_REVIEW1 L115 | Multiple Redis connections if all three are used together | Introduce shared cache store parameter or single `ApplicationContext` at composition root | small |
| R04 | dead-import (redundant block) | `infrastructure/cache_config.py:14-15` | Empty `if TYPE_CHECKING: pass` block | Review noise | Remove empty block | trivial |

### AI code smells

| ID | Pattern | Location | Evidence | Impact | Recommendation | Effort |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| A01 | ai-dual-implementation | `workflows.py` + `agent.py` | Workflow class has real port orchestration; LangGraph graph is a parallel skeleton with count-only nodes | Permanent branch until integrated; classic incremental-scaffold smell | Track as single integration task; avoid adding a third path (e.g. fat MCP tool) | medium |
| A02 | ai-app-any-escape | `application/agent.py:ainvoke_with_workflow_timeout` | `CompiledStateGraph[Any, Any, Any]`, `state: Any`, `-> Any` on unused helper | Weak contract on orchestration boundary | Add typed state alias when helper is wired | trivial |
| A03 | ai-todo-ship | `infrastructure/*_client.py` (3 files) | `raise NotImplementedError(...)` in production adapter methods | Runtime failure if called without mock/fake | Expected for scaffold; ensure MCP tools don't expose these paths until implemented | small |
| A04 | ai-placeholder-copy | `interface/custom_tools.py` | Module docstring: "Tool implementations deferred"; only `health_check` registered | Signals incomplete MCP surface | Replace with real tools or link to changelog increment ID | small |
| A05 | ai-kwargs-soup (latent) | `infrastructure/mcp_tool_cache.py:48` | `json.dumps({"result": result}, default=str)` with `# type: ignore` on deserialize | Non-round-trippable cache values for complex tool results | Use Pydantic envelope before wiring to tools | small |

## Severity rollup

### Critical

None. No silent data-loss paths on hot production routes; `health_check` is the only live MCP tool and infrastructure stubs are not reachable from it.

### High

- **H01** — `build_search_client` unwired; `ISearchClient` port has no production path
- **H02** — Composition factories (`build_document_video_workflow`, `build_mcp_tool_cache`) unused at entrypoint
- **H04** — `DocumentVideoWorkflow` orchestration disconnected from LangGraph agent
- **D01** — Duplicate orchestration between workflow class and skeleton graph nodes

### Medium

- **H06** — `log_level` setting with no consumer
- **H07** — Domain exception classes never raised
- **H08** — Validation schemas without MCP tool consumers
- **H09** — MCP tool cache helper unwired
- **R03** — Multiple `create_cache_store()` calls per composition
- **A01** — Dual implementation paths (workflow vs graph)

### Low

- **H03** — Empty `external_apis.py` placeholder
- **H05** — Unused `ainvoke_with_workflow_timeout` helper
- **D02**, **D03** — Symmetric adapter/cache patterns (acceptable at current scale)
- **D04** — Duplicated config defaults
- **R01**, **R02** — Thin facades (intentional)
- **R04** — Empty `TYPE_CHECKING` block
- **A02**–**A05** — Minor typing/placeholder smells

## Positive patterns observed

- Clean Architecture layer boundaries: application never imports infrastructure directly; Groq builder injected via `register_groq_model_builder()` in `wiring.py`
- Composition root centralizes adapter construction with cache-aside decorators
- Domain ports (`IDataRepository`, `ISearchClient`, `IVideoSearchClient`) are lean ABCs with focused methods
- `ruff check src/ tests/` and `mypy src/` pass with zero issues
- Tests use in-memory fakes (`CountingRepository`, `CountingSearchClient`) rather than heavy mocking
- `RedisCacheStore` degrades gracefully on connection failure (logs warning, returns cache miss)
- No `utils.py` / `helpers.py` dumping grounds; no broad `except Exception: pass` in business logic
- Local UI correctly restricts to loopback hosts and development `APP_ENV`

## Verification performed

- [x] Import graph from entrypoints (`main.py`, `local_ui_main.py`, `wiring.py`)
- [x] `uv run ruff check src/ tests/` — all passed
- [x] `uv run mypy src/` — success (36 files)
- [x] Changelog cross-check (`application/`, `infrastructure/`, `entrypoint/` CODE_REVIEW files)
- [x] `uv run pytest --collect-only` — 82 tests collected, no import errors

## Recommended remediation order

1. **Integrate orchestration paths (D01, H04, A01)** — Make LangGraph nodes delegate to `DocumentVideoWorkflow` (or inject the same ports) so there is one orchestration story.
2. **Wire composition root to entrypoint (H02, H09)** — When MCP tools ship, call `build_document_video_workflow()` and `build_mcp_tool_cache()` from `main()` or tool registration; pass a shared cache store (R03).
3. **Decide on web search path (H01)** — Either wire `build_search_client()` into agent/workflow or document explicit deferral.
4. **Resolve stale config (H06)** — Implement logging from `log_level` or remove the field.
5. **Activate or trim domain exceptions (H07)** — Raise from adapters when stubs are implemented.
6. **Wire validation schemas with MCP tools (H08)** — Implement `search_youtube` using existing `VideoSearchRequest`/`VideoSearchResponse`.
7. **Housekeeping (H03, H05, R04)** — Remove empty placeholder module/block and unused helper when integration PRs land.

## Out of scope / deferred

- Implementing Supabase/YouTube/DuckDuckGo adapter bodies (intentional `NotImplementedError` stubs)
- Documentation drift in `ARCHITECTURE.md` / `AGENTIC_ARCHITECTURE.md` (tracked in CODE_REVIEW1, not a code-health defect)
- `ui/` frontend bundle (separate from Python layer audit)
- Performance characteristics (see performance-auditor rubric)

## Verdict

**acceptable with known debt**

The scaffold is architecturally sound and lint-clean, but maintainability risk concentrates in **unintegrated parallel paths** between the composition root, `DocumentVideoWorkflow`, and the LangGraph skeleton. None of this blocks the current `health_check`-only MCP surface, but it will compound if new features are added on only one path. Prioritize consolidating orchestration before adding more MCP tools or agent nodes.
