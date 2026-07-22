# Implementation 1: Domain exception taxonomy + web search wiring (BL-009, BL-005)

**Date:** 2026-07-21
**Layer:** domain
**Investigation:** [INVESTIGATION1.md](./INVESTIGATION1.md)
**Status:** done

## Summary

Rename domain `ValidationError` to `DomainValidationError`, add pure invariant helpers, raise domain exceptions from infrastructure adapter guards, map `DomainError` subclasses to MCP protocol errors at the interface tool wrapper, and document deferred web-search wiring in `wiring.py` and `AGENTIC_ARCHITECTURE.md`.

## Checklist

- [x] **1.** Rename `ValidationError` → `DomainValidationError` in `domain/exceptions.py`; add optional message support
- [x] **2.** Create `domain/invariants.py` with `require_non_empty_text`, `require_positive_int`, `require_credential`
- [x] **3.** Add invariant guards to `SupabaseRepository.find_documents`
- [x] **4.** Add invariant guards to `DuckDuckGoSearchClient.search`
- [x] **5.** Add invariant guards to `YouTubeDataApiClient.search_videos`
- [x] **6.** Create `interface/error_mapping.py` with `raise_as_mcp_error(domain_error)`
- [x] **7.** Catch `DomainError` in `_cached_tool_invoke` and map via `raise_as_mcp_error`
- [x] **8.** Add `# deferred — web search` comment at `build_search_client` in `wiring.py`
- [x] **9.** Update `AGENTIC_ARCHITECTURE.md` with web search wiring deferral and target path
- [x] **10.** Extend `tests/test_domain_exceptions.py` with raise/catch and invariant tests
- [x] **11.** Update `tests/test_infrastructure_stubs.py` for validation error cases
- [x] **12.** Add interface error-mapping tests in `tests/test_interface_tools.py`
- [x] **13.** Run `uv run ruff check src/` and fix issues
- [x] **14.** Run `uv run mypy src/`
- [x] **15.** Run `uv run pytest`
- [x] **16.** Update investigation/implementation status to done

## Task details

### 6. Interface error mapping

- **File(s):** `interface/error_mapping.py`
- **Done when:** `ResourceNotFoundError` → `fastmcp.NotFoundError`; `DomainValidationError` → `mcp.McpError` code -32602; other `DomainError` → `fastmcp.ToolError`

### 8–9. BL-005 deferral

- **Done when:** Factory comment present; AGENTIC_ARCHITECTURE documents that `ISearchClient` wires into `langchain_tools.search_web` / optional sparse-doc enrichment when BL-022 lands — not into `DocumentVideoWorkflow` in this increment

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Remediation (CODE_REVIEW1 — Batch 5)

- [x] **R1.** Add adapter-level `require_positive_int` tests: T26d (Supabase), T27c (YouTube), T28c (DuckDuckGo)
- [x] **R2.** Add `test_t31_raise_as_mcp_error_maps_generic_domain_error_to_tool_error` for `ToolError` fallback
- [x] **R3.** Update `ARCHITECTURE.md` file tree with `domain/invariants.py` and `interface/error_mapping.py`
- [x] **R4.** Re-run `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Verification

```text
uv run ruff check src/   → pass (4 import-order fixes applied)
uv run mypy src/         → Success: no issues found in 44 source files
uv run pytest            → 133 passed
```

### Post-remediation verification

```text
uv run ruff check src/   → pass
uv run mypy src/         → Success: no issues found in 44 source files
uv run pytest            → 137 passed
```
