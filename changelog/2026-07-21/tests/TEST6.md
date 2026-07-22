# Test Inventory 6: Application orchestration and MCP tools (BL-001, BL-010, BL-011, BL-006, BL-013)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [application/INVESTIGATION2.md](../application/INVESTIGATION2.md), [application/IMPLEMENTATION2.md](../application/IMPLEMENTATION2.md), [application/CODE_REVIEW2.md](../application/CODE_REVIEW2.md), [interface/INVESTIGATION1.md](../interface/INVESTIGATION1.md), [interface/IMPLEMENTATION1.md](../interface/IMPLEMENTATION1.md), [interface/CODE_REVIEW1.md](../interface/CODE_REVIEW1.md)

## Scope

Homologate application increment 2 and interface increment 1 across five backlog tasks:

- **BL-001** — LangGraph nodes delegate to `DocumentVideoWorkflow`; skeleton count nodes removed; graph state carries document/video outputs
- **BL-010** — Parallel vs sequential branch selection in `retrieve_with_videos`
- **BL-011** — `ainvoke_with_workflow_timeout` wired for graph invocations; typed `DocumentVideoState`; timeout enforcement
- **BL-006** — `search_youtube`, `find_documents`, `run_workflow` MCP tools with Pydantic validation
- **BL-013** — `DocumentSummary` pruned payloads; no full `content` in JSON-RPC responses

Existing coverage from implementation: `tests/test_workflows.py` (T15–T19d), `tests/test_llm.py` (LLM05–LLM05c), `tests/test_interface_tools.py` (T20–T24), `tests/test_validation.py` (T08–T15). Prior inventories TEST1–TEST5 remain valid.

## Test catalog

### Application — graph integration (BL-001)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM05b | `test_llm05b_graph_nodes_delegate_to_document_video_workflow` | `run_document_video_graph` + `DocumentVideoState` | Wired `DocumentVideoWorkflow` with fakes | Graph returns `document_count`, `video_count`, `search_terms`, `documents`, `videos` from real port calls | Assert counts and `documents[0].title` match fake repo output |
| LLM05d | `test_llm05d_graph_has_delegation_nodes_not_skeleton` | `build_document_video_graph` node list | Compile graph | Nodes are `fetch_documents`, `derive_search_terms`, `search_videos`, `merge_results`; no `_count_*` skeleton nodes | Assert `get_graph().nodes` keys; exclude `__start__` / `__end__` |
| UI01 | `test_list_workflows_returns_langgraph_metadata` | `list_registered_workflows` graph metadata | GET `/api/workflows` | Graph view exposes LangGraph framework and start edge | Assert `framework == "langgraph"` and start node present |

### Application — parallel I/O (BL-010)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T19b | `test_t19b_parallel_io_when_no_documents` | `retrieve_with_videos` docstring — query-only path | Tracking fakes with sleep on doc fetch | Video search starts before document fetch completes | Assert `video_started_before_doc_finished` |
| T19c | `test_t19c_sequential_video_refetch_when_document_title_differs` | Title-correction branch | Doc title ≠ query | Second sequential YouTube call with document title | Assert `call_count == 2` and `last_query == title` |
| T19d | `test_t19d_skips_second_video_fetch_when_title_matches_query` | Optimistic parallel path when title matches | Doc title == query | Single video call; provisional results kept | Assert `call_count == 1` |
| T15–T19 | `test_t15`–`test_t19` | `retrieve_with_videos` routing | Fakes with limits | Title fallback, limits, tuple return | Assert port call args and return shape |

### Application — timeout and retry (BL-011)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM05 | `test_llm05_agent_nodes_use_workflow_execution_config` | `WorkflowExecutionConfig` → retry/timeout | Set config with known values | Merge nodes: `max_attempts = node_retries + 1`; read nodes: `max_attempts = 2` | Assert `_node_retry_policy()` and `_read_node_retry_policy()` |
| LLM05c | `test_llm05c_workflow_timeout_enforced` | `ainvoke_with_workflow_timeout` | `workflow_timeout_seconds=0.01`, slow repo | `asyncio.TimeoutError` on direct graph invoke | `pytest.raises(asyncio.TimeoutError)` |
| T26 | `test_t26_run_workflow_enforces_workflow_timeout` | `run_workflow` → `run_document_video_graph` → timeout helper | Same slow-repo setup via MCP tool | `asyncio.TimeoutError` when calling `run_workflow` | `pytest.raises` on tool call |

### Interface — MCP tools (BL-006)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T22 | `test_t22_search_youtube_returns_validated_response` | `search_youtube` + `VideoSearchResponse` | Wired workflow fake | Returns validated video list | Assert response type and video title |
| T23 | `test_t23_find_documents_returns_pruned_document_summaries` | `find_documents` + `DocumentQueryResponse` | Wired workflow fake | Documents as `DocumentSummary`; videos included | Assert summary fields; no `content` key |
| T24 | `test_t24_run_workflow_returns_graph_counts` | `run_workflow` + `WorkflowRunResponse` | Wired workflow fake | Returns counts, search_terms, documents, videos | Assert `document_count`, `video_count`, `search_terms` |
| T16 | `test_t16_document_query_request_validation` | `DocumentQueryRequest` field constraints | Invalid query/limits | `ValidationError` on empty query or out-of-range limits | `pytest.raises(ValidationError)` |
| T17 | `test_t17_workflow_run_request_validation` | `WorkflowRunRequest` field constraints | Invalid query/limits | `ValidationError` on empty query or out-of-range limits | `pytest.raises(ValidationError)` |
| T08–T14 | `test_t08`–`test_t14` | `VideoSearchRequest` / `VideoSearchResponse` | Boundary inputs | Defaults, bounds, empty query | Existing validation tests |

### Interface — pruned payloads (BL-013)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T15 | `test_t15_document_summary_prunes_content_to_snippet` | `document_hit_to_summary` | 250-char content, max 200 | Snippet truncated with `...`; only `id`, `title`, `snippet` in dump | Assert field set and length |
| T23 | `test_t23_find_documents_returns_pruned_document_summaries` | `find_documents` MCP boundary | Fake with long `content` | `content` absent from `model_dump()` | Assert `"content" not in summary.model_dump()` |
| T25 | `test_t25_run_workflow_omits_full_content_from_documents` | `run_workflow` MCP boundary | Fake with long `content` | `DocumentSummary` only; no `content` in response | Assert `model_dump()` keys and absence of `content` |

## Deferred (not testable yet)

- LangGraph path parallel I/O (BL-010 scoped to `retrieve_with_videos` only; graph runs sequentially by design — INVESTIGATION2)
- Local UI `POST /api/workflows/{id}/run` timeout path — same `run_document_video_graph` as MCP `run_workflow`; covered indirectly via T26
- `search_web`, `query_supabase_sql` MCP tools — out of scope per INVESTIGATION1
- Real HTTP adapter integration — BL-022 deferred
- `run_workflow` cache semantics for non-idempotent runs — product decision deferred

## Handoff to implementation

[IMPLEMENTATION6.md](./IMPLEMENTATION6.md)
