# Code Review 1: Domain exception taxonomy + web search wiring deferral (BL-009, BL-005)

**Date:** 2026-07-21
**Layer:** domain
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION1.md](./INVESTIGATION1.md)
- [IMPLEMENTATION1.md](./IMPLEMENTATION1.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| — | **No dedicated commits** — domain increment 1 exists as modified/untracked working-tree changes on `testbranch` |

**Working-tree files in scope (domain increment 1):**

| Path | Change |
| :--- | :--- |
| `src/mcp_server/domain/exceptions.py` | modified — `ValidationError` → `DomainValidationError` |
| `src/mcp_server/domain/invariants.py` | new (untracked) |
| `src/mcp_server/infrastructure/supabase_client.py` | modified — invariant guards |
| `src/mcp_server/infrastructure/search_client.py` | modified — invariant guards |
| `src/mcp_server/infrastructure/youtube_client.py` | modified — invariant guards |
| `src/mcp_server/interface/error_mapping.py` | new (untracked) |
| `src/mcp_server/interface/custom_tools.py` | modified — `DomainError` catch + MCP mapping |
| `src/mcp_server/wiring.py` | modified — `# deferred — web search` comment |
| `AGENTIC_ARCHITECTURE.md` | modified — BL-005 wiring deferral section |
| `tests/test_domain_exceptions.py` | modified — raise/catch + invariant tests |
| `tests/test_infrastructure_stubs.py` | modified — adapter guard cases |
| `tests/test_interface_tools.py` | modified — T29/T30 MCP error mapping |
| `changelog/2026-07-21/domain/` | new (untracked) — investigation + implementation |

## Summary

INVESTIGATION1 and IMPLEMENTATION1 are delivered on disk: domain `DomainValidationError` rename avoids Pydantic/FastMCP collision; pure `invariants.py` helpers enforce empty-query, positive-limit, and missing-credential rules; all three infrastructure stubs raise domain exceptions before `NotImplementedError`; the interface maps `DomainError` subclasses to MCP protocol errors in `_cached_tool_invoke`; BL-005 web-search wiring is explicitly deferred in `wiring.py` and `AGENTIC_ARCHITECTURE.md`. Layer boundaries are respected — domain has no outer-layer imports; adapters depend inward on invariants only. All quality gates pass (133 tests). Verdict is **approve with nits** — implementation matches plan, but the increment is uncommitted and adapter-level tests omit some invariant paths documented in investigation.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION1 | All scope (in) items delivered. Scope (out) respected: BL-022 HTTP adapters, BL-006 `search_web` tool, workflow `ISearchClient` injection, and backlog markdown update deferred. |
| IMPLEMENTATION1 | All 16 checklist items checked; status `done` matches code on disk. Error-mapping contract (`NotFoundError` / `McpError -32602` / `ToolError`) implemented as specified. |
| ARCHITECTURE.md | Layer rules honored. File tree omits `domain/invariants.py` and `interface/error_mapping.py` — doc drift only, not a boundary violation. |
| ENVIRONMENT_SETUP.md | No new deps; verification commands (`ruff`, `mypy`, `pytest`) all pass. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| Rename `ValidationError` → `DomainValidationError` | `domain/exceptions.py` uses `DomainValidationError` with collision docstring | match |
| `domain/invariants.py` pure helpers | `require_non_empty_text`, `require_positive_int`, `require_credential` — imports only `domain.exceptions` | match |
| Adapter guards (empty query, positive limits, credentials) | All three `*_client.py` call invariants before stub `NotImplementedError` | match |
| `interface/error_mapping.py` | `raise_as_mcp_error()` maps subclasses per implementation spec | match |
| `_cached_tool_invoke` catches `DomainError` | `custom_tools.py` logs + `raise_as_mcp_error(exc)` on `DomainError` | match |
| `# deferred — web search` in `wiring.py` | Present in `build_search_client` docstring (lines 101–103) | match |
| `AGENTIC_ARCHITECTURE.md` deferral | BL-005 section documents target path via `langchain_tools.search_web`, not `DocumentVideoWorkflow` | match |
| Extend domain, infrastructure, interface tests | T07b–T07h, T26b–T28b, T29–T30 added | partial |
| BL-022 / BL-006 / workflow injection | Not implemented | match (deferred) |
| Backlog markdown update | `backlog/BACKLOG.md` still references `ValidationError` | match (deferred per scope out) |

## Layer review (domain)

### Files reviewed

- `src/mcp_server/domain/exceptions.py` — `DomainError`, `ResourceNotFoundError`, `DomainValidationError`; no forbidden imports; message support via standard `Exception` args (verified in tests).
- `src/mcp_server/domain/invariants.py` — pure guard helpers; raises typed domain exceptions with actionable messages; strips whitespace on text/credential checks.
- `src/mcp_server/domain/__init__.py` — module docstring only; exceptions/invariants not re-exported (acceptable for current import style).

**Cross-layer files (per investigation scope, verified for domain integration):**

- `infrastructure/supabase_client.py`, `search_client.py`, `youtube_client.py` — guards delegate to domain invariants; credentials checked only where adapters hold secrets (Supabase, YouTube; not DuckDuckGo stub).
- `interface/error_mapping.py` — maps domain errors to FastMCP/MCP types at boundary only.
- `interface/custom_tools.py` — single catch site for tool-level domain error translation; non-domain exceptions still re-raise unchanged.
- `wiring.py` — `build_search_client` factory retained but not called from composition root; deferral documented.

### Architecture & patterns

- Domain layer is dependency-free (no MCP, LangChain, Supabase, or `os.environ`).
- Invariants live in exactly one place (`domain/invariants.py`); adapters reuse them — DRY aligned with ARCHITECTURE.md.
- Defense in depth: Pydantic schemas in `interface/validation.py` reject empty queries and non-positive limits at MCP boundary; domain invariants protect adapter entry points for direct/test/internal calls.
- `Cached*` wrappers delegate to inner ports without catching `DomainError` — domain exceptions propagate through cache-aside to `_cached_tool_invoke`.
- BL-005 correctly defers `ISearchClient` wiring; `DocumentVideoWorkflow` remains `IDataRepository` + `IVideoSearchClient` only.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O — MCP tools still validate via Pydantic before delegation
- [x] Port/adapter boundaries respected — infrastructure raises domain exceptions; interface maps them
- [x] No secrets in source or changelog
- [x] No Pydantic `ValidationError` name collision in domain
- [x] No generic `except Exception` swallowing `DomainError` in `_cached_tool_invoke`

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **Uncommitted increment** — Domain increment 1 (and paired infrastructure/interface/test changes) has no dedicated commit on `testbranch`; merge requires staging and committing before PR review can anchor SHAs.
- **Partial adapter invariant test coverage** — Investigation scope lists guards for empty query, non-positive limits, and missing credentials on all three adapters. Tests cover empty query and missing credentials (Supabase/YouTube) but not adapter-level `require_positive_int` rejection (e.g. `limit=0`, `max_results=0`). Invariant helper `require_positive_int` is unit-tested in `test_domain_exceptions.py` only.
- **Unmapped `ToolError` fallback untested** — `raise_as_mcp_error` maps bare `DomainError` subclasses to `fastmcp.ToolError`, but no current subclass exercises that branch and no test asserts it. Low risk today (only two concrete subclasses exist) but the mapping contract in IMPLEMENTATION1 task 6 is not fully homologated.
- **ARCHITECTURE.md file tree drift** — `domain/invariants.py` and `interface/error_mapping.py` not listed under File Structure; update when next architecture doc pass runs.

### Suggestions (consider)

- Add `test_t26d_supabase_rejects_non_positive_limit` (and equivalents for YouTube/DuckDuckGo) to close the investigation test gap at the adapter boundary.
- Add a direct unit test for `raise_as_mcp_error` with a minimal `DomainError` subclass to lock the `ToolError` fallback.
- Re-export `exceptions` and `invariants` from `domain/__init__.py` if public API discoverability becomes important.
- Update `backlog/BACKLOG.md` BL-009 checkbox text from `ValidationError` to `DomainValidationError` when the master agent runs backlog hygiene (explicitly deferred in investigation scope out).

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (44 source files) |
| `uv run pytest` | pass (133 passed) |

## Verdict

**approve with nits**

BL-009 domain exception taxonomy is active end-to-end: pure invariants in domain, adapter guards in infrastructure, MCP protocol mapping at the tool wrapper, and tests for hierarchy, invariant helpers, and the two primary error mappings (T29/T30). BL-005 deferral is documented without scope creep into `DocumentVideoWorkflow`. No critical blockers; commit the working tree and add adapter-level positive-limit / `ToolError` fallback tests before treating homologation as complete.
