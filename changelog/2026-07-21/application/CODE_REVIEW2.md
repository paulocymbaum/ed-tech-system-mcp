# Code Review 2: Workflow orchestration integration, parallel I/O, timeout/retry

**Date:** 2026-07-21
**Layer:** application
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION2.md](./INVESTIGATION2.md)
- [IMPLEMENTATION2.md](./IMPLEMENTATION2.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `c5b5a60` | Enhance LLM integration and operational configuration *(skeleton graph nodes; sequential `retrieve_with_videos`)* |
| `80bb4ce` | Add workflow-ui script and integrate FastAPI and Uvicorn dependencies *(local UI shell; no workflow I/O integration)* |

**Working tree (uncommitted):** Primary IMPLEMENTATION2 deliverables — `workflows.py` split + parallel gather, `agent.py` real nodes + typed timeout helper + `run_document_video_graph`, extended `tests/test_workflows.py` and `tests/test_llm.py`, changelog artifacts `INVESTIGATION2.md` / `IMPLEMENTATION2.md`.

## Summary

INVESTIGATION2 and IMPLEMENTATION2 are **delivered in the working tree**: `DocumentVideoWorkflow` exposes graph-delegable steps with optimistic parallel I/O in `retrieve_with_videos`; LangGraph nodes delegate to the wired workflow via `get_document_video_workflow()`; `ainvoke_with_workflow_timeout` is typed with `DocumentVideoState` and exercised by `run_document_video_graph`; read nodes use `RetryPolicy(max_attempts=2)`. Layer boundaries are respected — no infrastructure or MCP imports in application modules. Scoped and full pytest suites pass. Verdict is **request changes** because IMPLEMENTATION2 code and changelog files are **not committed** on `testbranch`; merge would ship skeleton graph and sequential workflow from HEAD.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION2 | All scope (in) items delivered in working tree. Scope (out) correctly deferred (`langchain_tools.py`, real HTTP adapters). |
| IMPLEMENTATION2 | Checklist complete; status `done` matches working-tree code. Local UI POST deviation cross-referenced to interface IMPLEMENTATION1. |
| ARCHITECTURE.md | Application depends on domain ports and LangGraph only; workflow orchestration in `workflows.py` / `agent.py` — aligned. |
| AGENTIC_ARCHITECTURE.md | Orchestration semantics match split-step graph + `run_document_video_graph`. **Drift:** file map still marks MCP tools and several validation schemas as planned. |
| BACKLOG.md | BL-001, BL-010, BL-011 tagged `done-2026-07-21` with checklist items satisfied by working-tree code. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| Split `workflows.py` — `fetch_documents`, `derive_search_terms`, `search_videos`, parallel `retrieve_with_videos` | Implemented in working tree; HEAD still sequential-only | partial (uncommitted) |
| Replace skeleton nodes with real workflow delegation | `_fetch_documents`, `_derive_search_terms`, `_search_videos` call workflow methods; skeleton `_count_*` removed | match (uncommitted) |
| Type `ainvoke_with_workflow_timeout` with `DocumentVideoState` | `DocumentVideoGraph` alias; helper typed; `cast` on return | match (uncommitted) |
| Read-node retry cap = 2 | `_read_node_retry_policy()` on `fetch_documents` / `search_videos` | match (uncommitted) |
| `run_document_video_graph()` for interface | Exported; used by interface `run_workflow` and local UI | match (uncommitted) |
| `tests/test_workflows.py` parallel vs sequential branch tests | `test_t19b`–`test_t19d` added | match (uncommitted) |
| `tests/test_llm.py` integrated graph + timeout tests | `test_llm05b`, `test_llm05c` added | match (uncommitted) |
| Deferred: `langchain_tools.py` wrappers | Not implemented | match (deferred) |

## Layer review (application)

### Files reviewed

- `src/mcp_server/application/workflows.py` — split steps; optimistic `asyncio.gather` with title-correction re-fetch; latency docstring
- `src/mcp_server/application/agent.py` — real async nodes; tiered retry; typed timeout helper; `run_document_video_graph`; extended `DocumentVideoState` with `documents` / `videos`
- `src/mcp_server/application/workflow_runtime.py` — runtime accessor used by nodes (BL-002 prerequisite)
- `tests/test_workflows.py` — parallel overlap, sequential re-fetch, skip-second-fetch branches
- `tests/test_llm.py` — graph delegation, timeout enforcement, read vs merge retry assertions

### Architecture & patterns

- Graph nodes resolve `DocumentVideoWorkflow` through `get_document_video_workflow()` — no direct port or infrastructure imports.
- `retrieve_with_videos` parallel path matches performance audit P01 recommendation; sequential re-fetch when first-document title differs from query.
- `ainvoke_with_workflow_timeout` wraps `asyncio.wait_for` with `workflow_timeout_seconds()` from `WorkflowExecutionConfig`.
- `derive_search_terms` and `merge_results` use full node retry budget; external read nodes capped at 2 attempts per BL-011.
- **Behavioral split:** LangGraph path (`run_document_video_graph`) runs fetch → derive → search **sequentially**; `retrieve_with_videos` uses parallel I/O. Investigation scoped parallel gather to the workflow method; graph does not reuse `retrieve_with_videos`.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **IMPLEMENTATION2 deliverables are uncommitted.** At HEAD, `agent.py` still has skeleton `_count_documents` / `_count_videos` nodes and `workflows.py` is sequential-only. `INVESTIGATION2.md` and `IMPLEMENTATION2.md` are untracked. Merging `testbranch` as-is would not ship BL-001, BL-010, or BL-011 application work.

### Warnings (should fix)

- **LangGraph path lacks BL-010 parallel I/O.** `run_document_video_graph` / MCP `run_workflow` execute sequential port calls while `find_documents` (interface) calls parallel `retrieve_with_videos`. Same domain capability with different latency — document or add a follow-up if intentional.
- **`AGENTIC_ARCHITECTURE.md` drift.** Tool taxonomy and validation schema tables still mark `DocumentQueryRequest`, `WorkflowRunRequest`, and MCP tools as planned despite interface increment delivering them.
- **Committed vs working-tree gap.** Review evidence spans `c5b5a60` skeleton state plus uncommitted integration; commit message history does not yet describe IMPLEMENTATION2.

### Suggestions (consider)

- Add an integration test asserting `run_workflow` MCP tool path times out (today only `ainvoke_with_workflow_timeout` direct call is tested).
- `derive_search_terms` node uses merge retry policy on a pure computation step — a single-attempt policy would reduce tail latency on transient graph errors.
- Consider consolidating graph execution with `retrieve_with_videos` or documenting why graph and composite workflow paths remain separate.

## Verification

| Command | Result |
| :--- | :--- |
| `uv sync --frozen` | pass |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass |
| `uv run pytest tests/test_workflows.py tests/test_llm.py` | pass (36 tests) |
| `uv run pytest` | pass (97 tests) |

## Verdict

**request changes**

Working-tree code matches INVESTIGATION2 / IMPLEMENTATION2, respects Clean Architecture, passes all quality gates, and satisfies BACKLOG BL-001, BL-010, BL-011 checklists. **Commit** application changes, tests, and changelog artifacts before merge; optionally document or align graph vs `retrieve_with_videos` latency behavior.
