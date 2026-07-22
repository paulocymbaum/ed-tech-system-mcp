# Code Review 1: MCP tools and pruned response payloads

**Date:** 2026-07-21
**Layer:** interface
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `80bb4ce` | Add workflow-ui script and integrate FastAPI and Uvicorn dependencies *(local UI FastAPI shell; `list_registered_workflows` GET routes)* |

**Working tree (uncommitted):** Primary IMPLEMENTATION1 deliverables — `validation.py` DTOs, `custom_tools.py` tools + cache wrapper, `main.py` tool imports, `local_ui/api.py` POST run endpoint, `tests/test_interface_tools.py` and `tests/test_validation.py`, changelog artifacts `INVESTIGATION1.md` / `IMPLEMENTATION1.md`.

## Summary

INVESTIGATION1 and IMPLEMENTATION1 are **delivered in the working tree**: pruned `DocumentSummary` DTO with mapping helpers; `search_youtube`, `find_documents`, and `run_workflow` MCP tools with Pydantic validation and `McpToolInteractionCache` wrapper; entrypoint imports register all tools; local UI `POST /api/workflows/{id}/run` delegates to `run_document_video_graph` with pruned responses. Tools are thin — they delegate to application workflow/graph without infrastructure calls. Full `DocumentHit.content` is omitted from MCP JSON-RPC payloads (BL-013). Verdict is **request changes** because IMPLEMENTATION1 code and changelog files are **not committed**; HEAD still exposes only a synchronous `health_check` placeholder.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | Scope (in) delivered in working tree. Local UI POST was scope (out) in investigation but added in implementation — documented in IMPLEMENTATION1 summary and IMPLEMENTATION2 deviation. |
| IMPLEMENTATION1 | Checklist complete except item 8 tags only BL-006 and BL-013 (BL-011 interface work delivered but not tagged in checklist). Status `done` matches working-tree code. |
| ARCHITECTURE.md | Pydantic validation before application calls; thin MCP decorators; no Supabase/YouTube in tools — aligned. |
| AGENTIC_ARCHITECTURE.md | Tool taxonomy matches `search_youtube`, `find_documents`, `run_workflow` contracts. **Drift:** schema and file-map entries still marked planned. |
| BACKLOG.md | BL-006, BL-013, BL-011 (interface portion) tagged `done-2026-07-21` with checklist items satisfied by working-tree code. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `DocumentSummary`, query/workflow schemas, mapping in `validation.py` | `DocumentSummary`, `DocumentQuery*`, `WorkflowRun*`, `document_hit_to_summary` | match (uncommitted) |
| `search_youtube`, `find_documents`, `run_workflow` in `custom_tools.py` | Implemented with `_cached_tool_invoke` wrapper | match (uncommitted) |
| Import new tools in `main.py` | Side-effect imports for all four tools | match (uncommitted) |
| `tests/test_interface_tools.py` behavior tests | T20–T24: health, cache, tools, pruned docs, graph counts | match (uncommitted) |
| `tests/test_validation.py` DocumentSummary test | `test_t15_document_summary_prunes_content_to_snippet` | match (uncommitted) |
| Deferred: `search_web`, `query_supabase_sql` | Not implemented | match (deferred) |
| Deferred: local UI POST (investigation) | `local_ui/api.py` POST run added | extra (documented deviation) |

## Layer review (interface)

### Files reviewed

- `src/mcp_server/interface/validation.py` — pruned `DocumentSummary`; request/response schemas; 200-char snippet truncation
- `src/mcp_server/interface/custom_tools.py` — thin async tools; Pydantic request construction; cache-aside via `get_mcp_tool_cache()`
- `src/mcp_server/main.py` — registers `find_documents`, `run_workflow`, `search_youtube` alongside `health_check`
- `src/mcp_server/interface/local_ui/api.py` — `POST /api/workflows/{workflow_id}/run` with `WorkflowRunRequest` / `WorkflowRunResponse` (BL-011 local UI path)
- `tests/test_interface_tools.py` — tool behavior, cache hit, pruned payload assertions
- `tests/test_validation.py` — `DocumentSummary` pruning contract

### Architecture & patterns

- MCP tools validate inputs via Pydantic request models before calling application layer.
- `find_documents` delegates to `DocumentVideoWorkflow.retrieve_with_videos`; `run_workflow` delegates to `run_document_video_graph` — no infrastructure imports in interface tools.
- `document_hits_to_summaries` applied at tool and local UI boundaries; `content` field never exposed in MCP responses.
- `health_check` corrected to `async def` with cache wrapper (committed HEAD had sync stub incompatible with async cache path).
- `run_workflow` and `find_documents` share cache wrapper — identical args return cached results (inherited from BL-002; acceptable for idempotent reads but worth noting for workflow runs).

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected (delegation to application only)
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **IMPLEMENTATION1 deliverables are uncommitted.** At HEAD, `custom_tools.py` contains only a synchronous `health_check` placeholder and `validation.py` lacks `DocumentSummary` / workflow schemas. `INVESTIGATION1.md` and `IMPLEMENTATION1.md` are untracked. Merging `testbranch` as-is would not ship BL-006, BL-013, or BL-011 interface work.

### Warnings (should fix)

- **INVESTIGATION1 scope drift for local UI POST.** Investigation listed local UI run endpoint as scope (out); IMPLEMENTATION1 added `POST /api/workflows/{id}/run` in `local_ui/api.py`. Behavior is correct and cross-referenced, but investigation was not updated to reflect the decision.
- **IMPLEMENTATION1 checklist omits BL-011 tag.** Item 8 tags BL-006 and BL-013 only; BL-011 interface checklist items in BACKLOG.md are satisfied but not mirrored in implementation checklist.
- **`AGENTIC_ARCHITECTURE.md` drift.** `DocumentQueryRequest`, `WorkflowRunRequest`, and MCP tool file-map entries still marked planned.
- **`find_documents` vs `run_workflow` behavioral divergence.** `find_documents` uses parallel `retrieve_with_videos`; `run_workflow` uses sequential LangGraph path — clients may see different latency for semantically similar discovery (see application CODE_REVIEW2).

### Suggestions (consider)

- Add a `test_interface_tools.py` case asserting `run_workflow` omits full `content` from documents (covered indirectly via `find_documents` test).
- Document whether caching `run_workflow` results is desirable for production or should be excluded from cache rules.
- Update INVESTIGATION1 status/scope to include local UI POST if the deviation is permanent.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass |
| `uv run pytest tests/test_interface_tools.py tests/test_validation.py` | pass (13 tests) |
| `uv run pytest` | pass (97 tests) |

## Verdict

**request changes**

Working-tree code matches INVESTIGATION1 / IMPLEMENTATION1 intent, respects validation and anti-pattern rules, prunes MCP payloads per BL-013, and passes all quality gates. **Commit** interface changes, tests, and changelog artifacts before merge; update investigation scope note for local UI POST and tag BL-011 in IMPLEMENTATION1 checklist for traceability.
