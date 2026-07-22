# Implementation 2: Infrastructure trivial cleanup (BL-026, BL-025, BL-024)

**Date:** 2026-07-21
**Layer:** infrastructure
**Investigation:** [INVESTIGATION2.md](./INVESTIGATION2.md)
**Status:** done

## Summary

Removed dead `TYPE_CHECKING` scaffolding from `cache_config.py`, deleted unused `external_apis.py`, and documented the async-only `CachedChatModel` cache contract in `cached_llm.py` and `AGENTIC_ARCHITECTURE.md`. Updated architecture file trees in `ARCHITECTURE.md` and `AGENTIC_ARCHITECTURE.md`.

## Checklist

- [x] **1.** BL-026: Remove `if TYPE_CHECKING: pass` and unused `TYPE_CHECKING` import from `cache_config.py`
- [x] **2.** BL-025: Delete `src/mcp_server/infrastructure/external_apis.py`
- [x] **3.** BL-025: Remove `external_apis.py` from `ARCHITECTURE.md` file tree
- [x] **4.** BL-025: Remove `external_apis.py` from `AGENTIC_ARCHITECTURE.md` file tree
- [x] **5.** BL-024: Expand `CachedChatModel` class docstring in `cached_llm.py` (async-only cache; sync bypass; deferral)
- [x] **6.** BL-024: Add LLM cache async contract note in `AGENTIC_ARCHITECTURE.md` (infrastructure section)
- [x] **7.** Run `uv run ruff check src/` and fix issues
- [x] **8.** Run `uv run mypy src/`
- [x] **9.** Run `uv run pytest`
- [x] **10.** Set investigation status `approved`; set implementation status `done`

## Task details

### 1. BL-026 — cache_config cleanup

- **File(s):** `src/mcp_server/infrastructure/cache_config.py`
- **Done when:** No `TYPE_CHECKING` import or empty block; file unchanged otherwise

### 2–4. BL-025 — external_apis removal

- **File(s):** `external_apis.py`, `ARCHITECTURE.md`, `AGENTIC_ARCHITECTURE.md`
- **Done when:** File deleted; both doc trees have no `external_apis.py` entry

### 5–6. BL-024 — async-only LLM cache documentation

- **File(s):** `cached_llm.py`, `AGENTIC_ARCHITECTURE.md`
- **Done when:** Docstring and architecture doc state `_agenerate` caches, `_generate` does not; sync cache deferred

## Verification results

```text
uv run ruff check src/  → All checks passed!
uv run mypy src/        → Success: no issues found in 39 source files
uv run pytest           → 102 passed, 1 warning in 2.95s
```

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged
- [x] Changes match ARCHITECTURE.md layer rules

## Deferred (from investigation)

- Sync `_generate` cache path — add only when sync LLM callers are introduced in production

## Remediation (Stage 3 — CODE_REVIEW2)

**Source:** [CODE_REVIEW2.md](./CODE_REVIEW2.md) (verdict: approve with nits)
**Status:** done

### Remediation checklist

- [x] **R1.** Document `record_cache_hit` / `record_cache_miss` observability hooks in `cached_llm.py` (intentional; not BL-024 doc-only scope). Verified covered by `tests/test_cache.py::test_c24_cached_llm_logs_hit_on_second_call` — no revert.
- [x] **R2.** Align `ARCHITECTURE.md` file-tree comment for `cached_llm.py` with async `_agenerate`-only contract (match `AGENTIC_ARCHITECTURE.md` wording).
- [x] **R3.** Run `uv run ruff check src/`
- [x] **R4.** Run `uv run mypy src/`
- [x] **R5.** Run `uv run pytest`

### Deferred (remediation)

- **Uncommitted delivery** — increment 2 changes remain uncommitted on `testbranch`; procedural; master/user handles isolated commit before merge (per CODE_REVIEW2 warning; not in increment scope).

### Remediation verification results

```text
uv run ruff check src/  → All checks passed!
uv run mypy src/        → Success: no issues found in 39 source files
uv run pytest           → 102 passed, 1 warning in 2.93s
```
