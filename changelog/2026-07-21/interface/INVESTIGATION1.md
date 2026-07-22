# Investigation 1: MCP tools and pruned response payloads

**Date:** 2026-07-21
**Layer:** interface
**Status:** approved

## User request

Implement BL-006 (MCP tools beyond `health_check`), BL-013 (prune MCP response payloads), and interface portion of BL-011 (`run_workflow` with timeout helper).

## Architecture alignment

- **Layers touched:** interface (primary), application (`run_document_video_graph` from application increment)
- **Patterns applied:** Pydantic validation before/after application calls; `DocumentSummary` DTO at MCP boundary; thin tool decorators delegating to workflows; MCP tool cache wrapper
- **Anti-patterns avoided:** No Supabase/YouTube calls in tools; no full `DocumentHit.content` in JSON-RPC responses

## Current state

| Asset | Status |
| :--- | :--- |
| `custom_tools.py` | Only `health_check` registered |
| `validation.py` | `VideoSearchRequest`/`Response` exist; no document or workflow schemas |
| `tests/test_interface_tools.py` | Health check + cache only |
| `AGENTIC_ARCHITECTURE.md` | Documents target tools: `find_documents`, `search_youtube`, `run_workflow` |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No `search_youtube` / `find_documents` tools | interface | P0 |
| No `run_workflow` with timeout | interface | P0 |
| No `DocumentSummary` pruned DTO | interface | P0 |
| `main.py` imports only `health_check` | entrypoint | P1 |

## Minimal increment

Add `DocumentSummary`, `DocumentQueryRequest`/`Response`, `WorkflowRunRequest`/`Response` in `validation.py`; implement three MCP tools in `custom_tools.py` with cache wrapper; map `DocumentHit` → `DocumentSummary` at tool boundary; add behavior tests.

### Scope (in)

- `interface/validation.py` — DTOs + mapping helper
- `interface/custom_tools.py` — `search_youtube`, `find_documents`, `run_workflow`
- `main.py` — import new tools for registration
- `interface/local_ui/api.py` — `POST /api/workflows/{id}/run` with pruned `WorkflowRunResponse` (BL-011 local UI path; delegates to `run_document_video_graph` with timeout enforcement)
- `tests/test_interface_tools.py`, `tests/test_validation.py` — behavior + schema tests

### Scope (out / deferred)

- `search_web`, `query_supabase_sql` tools

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `interface/validation.py` | modify | Pruned DTOs + workflow schemas |
| `interface/custom_tools.py` | modify | Register tools |
| `main.py` | modify | Tool import side effects |
| `tests/test_interface_tools.py` | modify | Tool behavior tests |
| `tests/test_validation.py` | modify | DocumentSummary schema test |

## Dependencies & environment

- Depends on application INVESTIGATION2 (`run_document_video_graph`, workflow methods)
- Commands: `uv run pytest tests/test_interface_tools.py tests/test_validation.py`

## Handoff to implementation

IMPLEMENTATION1.md: validation schemas first, then tools, then tests.
