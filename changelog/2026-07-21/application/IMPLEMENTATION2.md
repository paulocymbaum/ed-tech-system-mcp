# Implementation 2: Workflow orchestration integration, parallel I/O, timeout/retry

**Date:** 2026-07-21
**Layer:** application
**Investigation:** [INVESTIGATION2.md](./INVESTIGATION2.md)
**Status:** done

## Summary

Split `DocumentVideoWorkflow` into graph-delegable steps with parallel query-only I/O; replaced skeleton LangGraph nodes with real workflow delegation; typed and wired `ainvoke_with_workflow_timeout`; tiered retry policies (2 attempts on read nodes, full budget on merge/derive).

## Checklist

- [x] **1.** Split `workflows.py` — `fetch_documents`, `derive_search_terms`, `search_videos`, parallel `retrieve_with_videos`
- [x] **2.** Refactor `agent.py` — real nodes, extended state, typed timeout helper, `run_document_video_graph`
- [x] **3.** Update `tests/test_workflows.py` — parallel vs sequential branch tests
- [x] **4.** Update `tests/test_llm.py` — integrated graph path + timeout enforcement test
- [x] **5.** Run `uv run ruff check src/` and fix issues
- [x] **6.** Run `uv run mypy src/`
- [x] **7.** Run `uv run pytest`
- [x] **8.** Update investigation status; tag BL-001, BL-010, BL-011 in BACKLOG.md

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed
- [x] Changes match ARCHITECTURE.md layer rules

## Deviations

- Local UI `POST /api/workflows/{id}/run` added in interface layer (cross-ref IMPLEMENTATION1) to satisfy BL-011 local UI path.

## Remediation

**Date:** 2026-07-21 (post CODE_REVIEW2)

- [x] Document uncommitted state — merge requires commit; user explicitly deferred
- [x] Clarify LangGraph sequential path vs BL-010 parallel I/O in `agent.py` / `workflows.py` docstrings and INVESTIGATION2
- [x] Update `AGENTIC_ARCHITECTURE.md` — delivered MCP tools and validation schemas
