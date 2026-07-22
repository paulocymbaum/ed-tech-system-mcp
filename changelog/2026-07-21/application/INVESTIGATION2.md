# Investigation 2: Workflow orchestration integration, parallel I/O, timeout/retry

**Date:** 2026-07-21
**Layer:** application
**Status:** approved

## User request

Implement BL-001 (integrate LangGraph nodes with `DocumentVideoWorkflow`), BL-010 (parallelize independent workflow I/O), and BL-011 (enforce workflow timeout and retry policy on graph invocations).

## Architecture alignment

- **Layers touched:** application (primary), interface (cross-ref for `run_workflow` timeout wiring in interface increment)
- **Patterns applied:** Graph nodes delegate to use-case orchestrator via `get_document_video_workflow()`; `ainvoke_with_workflow_timeout()` enforces overall graph budget; read-only nodes get lower retry cap; `DocumentVideoState` typed throughout timeout helper
- **Anti-patterns avoided:** No direct infrastructure imports in graph nodes; no MCP types in application layer

## Current state

| Asset | Status |
| :--- | :--- |
| `workflows.py` | `retrieve_with_videos()` sequential only; no split methods for graph nodes |
| `agent.py` | Skeleton `_count_documents` / `_count_videos` nodes; `ainvoke_with_workflow_timeout` unused with `Any` types |
| `workflow_runtime.py` | Runtime accessor wired at composition root (BL-002 done) |
| `tests/test_workflows.py` | Contract tests for sequential workflow only |
| `tests/test_llm.py` | Graph build + retry config; no integrated I/O or timeout tests |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Graph nodes don't call real workflow I/O | application | P0 |
| Sequential-only `retrieve_with_videos` | application | P0 |
| `ainvoke_with_workflow_timeout` dead code | application | P0 |
| No parallel vs sequential branch tests | tests | P0 |
| `Any` on timeout helper state/graph | application | P1 |

## Minimal increment

Split `DocumentVideoWorkflow` into fetch/derive/search steps usable by LangGraph nodes; replace skeleton count nodes with real delegation; add optimistic `asyncio.gather` for query-only video path with title-correction re-fetch when documents exist; type and wire `ainvoke_with_workflow_timeout`; lower read-node retries to 2 attempts; add `run_document_video_graph()` helper for interface `run_workflow` tool.

### Scope (in)

- `workflows.py` — split methods, parallel gather, docstring
- `agent.py` — real nodes, typed timeout helper, retry tiers
- `tests/test_workflows.py` — parallel/sequential branch tests
- `tests/test_llm.py` — integrated graph + timeout tests

### Scope (out / deferred)

- Local UI POST run endpoint (interface increment handles BL-011 local UI path if needed)
- Real HTTP adapters (BL-022)
- `langchain_tools.py` wrappers

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `application/workflows.py` | modify | Split steps + parallel I/O |
| `application/agent.py` | modify | Integrate workflow; timeout/retry |
| `tests/test_workflows.py` | modify | Parallel/sequential tests |
| `tests/test_llm.py` | modify | Graph integration + timeout |

## Dependencies & environment

- No new runtime deps
- Commands: `uv run pytest tests/test_workflows.py tests/test_llm.py`

## Risks & open questions

- Optimistic parallel gather may issue an extra YouTube call when document title differs from query — acceptable per performance audit P01
- **Graph vs composite latency:** LangGraph path (`run_document_video_graph`) intentionally runs fetch → derive → search **sequentially** for step visibility in graph traces and the local workflow UI. BL-010 parallel I/O is scoped to `retrieve_with_videos` (MCP `find_documents`); aligning the graph path would sacrifice per-node observability and is deferred

## Handoff to implementation

IMPLEMENTATION2.md: ordered tasks domain→application→tests→verification gates.
