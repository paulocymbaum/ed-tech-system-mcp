# Investigation 1: Domain exception taxonomy + web search wiring (BL-009, BL-005)

**Date:** 2026-07-21
**Layer:** domain
**Status:** done

## User request

Execute backlog tasks BL-009 and BL-005 together:

- **BL-009:** Activate domain exception taxonomy — raise from adapters, rename `ValidationError` if Pydantic collision, map at interface boundary, extend tests.
- **BL-005:** Decide whether to wire `build_search_client()` into agent/workflow or document deferral; update `AGENTIC_ARCHITECTURE.md`.

## Architecture alignment

- **Layers touched:** domain (primary), infrastructure (adapter guards), interface (MCP error mapping), application (no workflow change for BL-005)
- **Patterns applied:** Domain invariants in pure helpers; adapters raise domain exceptions before stub `NotImplementedError`; interface maps `DomainError` → FastMCP/MCP protocol errors at tool boundary
- **Anti-patterns avoided:** No Pydantic `ValidationError` name collision in domain; no infrastructure imports in domain; no generic `except Exception` swallowing domain errors in tools

## Current state

| Asset | Status |
| :--- | :--- |
| `domain/exceptions.py` | `DomainError`, `ResourceNotFoundError`, `ValidationError` defined but never raised |
| Infrastructure adapters | Stubs raising `NotImplementedError` only; no input guards |
| `interface/custom_tools.py` | `_cached_tool_invoke` logs and re-raises all exceptions unchanged |
| `wiring.py:build_search_client` | Factory exists; zero production callers; docstring notes deferral |
| `DocumentVideoWorkflow` | Uses `IDataRepository` + `IVideoSearchClient` only — no `ISearchClient` |
| `tests/test_domain_exceptions.py` | Hierarchy `isinstance` checks only (T07) |
| `tests/test_infrastructure_stubs.py` | Expects `NotImplementedError` for valid inputs (T26–T28) |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| `ValidationError` collides with Pydantic/FastMCP | domain | P0 |
| No invariant guards on adapter inputs | infrastructure | P0 |
| No MCP error mapping for domain failures | interface | P0 |
| `build_search_client` unwired | wiring / application | P1 — defer (BL-022 stubs) |
| Domain exception raise/catch tests missing | tests | P0 |

## Minimal increment

Rename domain `ValidationError` → `DomainValidationError`. Add `domain/invariants.py` with pure guard helpers. Call guards from all three infrastructure adapters (empty query, non-positive limits, missing credentials → `ResourceNotFoundError`). Add `interface/error_mapping.py` and wrap domain errors in `_cached_tool_invoke`. **Defer** wiring `build_search_client()` — document target injection point in `AGENTIC_ARCHITECTURE.md` and mark factory with `# deferred — web search`. Full DuckDuckGo implementation remains BL-022.

### Scope (in)

- `domain/exceptions.py` — rename + message support
- `domain/invariants.py` — new pure validation helpers
- `infrastructure/supabase_client.py`, `search_client.py`, `youtube_client.py` — raise domain exceptions
- `interface/error_mapping.py` — map to FastMCP `NotFoundError` / `McpError` (-32602)
- `interface/custom_tools.py` — catch `DomainError` in `_cached_tool_invoke`
- `wiring.py` — `# deferred — web search` comment
- `AGENTIC_ARCHITECTURE.md` — document deferral and future wiring path
- `tests/test_domain_exceptions.py`, `tests/test_infrastructure_stubs.py`, `tests/test_interface_tools.py`

### Scope (out / deferred)

- BL-022 full adapter HTTP implementation (stubs keep `NotImplementedError` after guards)
- BL-006 `search_web` MCP tool
- Injecting `ISearchClient` into `DocumentVideoWorkflow` or LangGraph nodes
- Backlog markdown update (master agent)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `domain/exceptions.py` | modify | Rename `ValidationError` → `DomainValidationError`; optional message on base |
| `domain/invariants.py` | create | Shared invariant checks |
| `infrastructure/*_client.py` | modify | Raise domain errors before stub |
| `interface/error_mapping.py` | create | MCP boundary mapping |
| `interface/custom_tools.py` | modify | Apply mapping in tool invoke wrapper |
| `wiring.py` | modify | Explicit deferral comment (BL-005) |
| `AGENTIC_ARCHITECTURE.md` | modify | Document web search wiring decision |
| `tests/test_domain_exceptions.py` | modify | Raise/catch + invariant tests |
| `tests/test_infrastructure_stubs.py` | modify | Validation error cases |
| `tests/test_interface_tools.py` | modify | MCP error mapping behavior |

## Dependencies & environment

- No new runtime deps
- Commands: `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- FastMCP default server has no `ErrorHandlingMiddleware`; mapping raises `fastmcp.NotFoundError` and `mcp.McpError` directly in `_cached_tool_invoke` for predictable tool error responses.
- Empty search results are **not** `ResourceNotFoundError` — only missing credentials/config or explicit resource absence; empty lists remain valid success responses per AGENTIC_ARCHITECTURE.

## Handoff to implementation

IMPLEMENTATION1.md: domain rename + invariants → adapters → interface mapping → wiring comment + doc → tests → verification gates.
