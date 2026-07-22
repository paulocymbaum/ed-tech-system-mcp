# Code Review 2: Infrastructure trivial cleanup (BL-026, BL-025, BL-024)

**Date:** 2026-07-21
**Layer:** infrastructure
**Branch:** testbranch
**Base:** main (`c6d1a8a`)
**Status:** final

## Changelog references

- [INVESTIGATION2.md](./INVESTIGATION2.md)
- [IMPLEMENTATION2.md](./IMPLEMENTATION2.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| — | **No commits** — increment 2 exists only as unstaged working-tree changes on `testbranch` |

**Working-tree files in scope (infrastructure increment 2):**

| Path | Change |
| :--- | :--- |
| `src/mcp_server/infrastructure/cache_config.py` | modified (BL-026) |
| `src/mcp_server/infrastructure/external_apis.py` | deleted (BL-025) |
| `src/mcp_server/infrastructure/cached_llm.py` | modified (BL-024 + observability) |
| `ARCHITECTURE.md` | modified (BL-025 file tree) |
| `AGENTIC_ARCHITECTURE.md` | modified (BL-024/025 docs) |

## Summary

Infrastructure increment 2 delivers all three backlog items: dead `TYPE_CHECKING` scaffolding removed from `cache_config.py`, unused `external_apis.py` deleted with doc trees updated, and the async-only `CachedChatModel` cache contract documented in both `cached_llm.py` and `AGENTIC_ARCHITECTURE.md`. Layer boundaries remain clean — infrastructure depends on domain cache ports and LangChain adapters only. All verification gates pass (102 tests). Verdict is **approve with nits** — delivery is correct and documentation matches runtime behavior, but the increment is uncommitted, `cached_llm.py` includes observability hooks outside the investigation scope, and `ARCHITECTURE.md` does not echo the async-only note on the `cached_llm.py` tree entry.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION2 | Scope delivered: BL-026/025/024 checklist items match code. Deferred items respected (no sync cache path, no backlog edits, no `CODE_HEALTH_AUDIT1` update). |
| IMPLEMENTATION2 | All 10 checklist items checked; status `done` is accurate for implementation quality. Does not mention `record_cache_hit` / `record_cache_miss` additions in `cached_llm.py`. |
| ARCHITECTURE.md | `external_apis.py` removed from file tree. Tree also adds `cache_envelope.py` and `cache_observability.py` (doc sync from sibling work, not named in INVESTIGATION2). `cached_llm.py` comment still generic — no async-only qualifier. |
| AGENTIC_ARCHITECTURE.md | New **LLM completion cache** section accurately states `_agenerate` caches and `_generate` bypasses; table and env references match code. File tree removes `external_apis.py` and annotates `cached_llm.py` as async-only. Additional edits (MCP tool catalog, validation map, module status) exceed INVESTIGATION2 scope but are internally consistent with current branch state. |
| ENVIRONMENT_SETUP.md | Unchanged by this increment; no env-var drift introduced. |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| BL-026: Remove `TYPE_CHECKING` block from `cache_config.py` | `TYPE_CHECKING` import and empty block removed; file otherwise unchanged | match |
| BL-025: Delete `external_apis.py` | File deleted; zero `src/` importers | match |
| BL-025: Remove `external_apis.py` from `ARCHITECTURE.md` tree | Removed; tree also lists `cache_envelope.py`, `cache_observability.py` | partial (extra tree entries) |
| BL-025: Remove `external_apis.py` from `AGENTIC_ARCHITECTURE.md` tree | Removed from infrastructure tree | match |
| BL-024: Expand `CachedChatModel` class docstring | Docstring documents async-only contract and sync deferral | match |
| BL-024: Add LLM cache section in `AGENTIC_ARCHITECTURE.md` | Section with path table, TTL env refs, wiring context | match |
| Run `ruff`, `mypy`, `pytest` | All pass (102 tests) | match |
| Scope out: sync `_generate` cache | `_generate` still pass-through only | match |
| Scope out: `backlog/BACKLOG.md` updates | Backlog checkboxes still open (expected per investigation) | match |
| — | `cached_llm.py` adds `record_cache_hit` / `record_cache_miss` on cache paths | extra |
| — | Broad `AGENTIC_ARCHITECTURE.md` edits (tool catalog, validation map, status tables) | extra |

## Layer review (infrastructure)

### Files reviewed

- `src/mcp_server/infrastructure/cache_config.py` — BL-026 dead-code removal; `CacheSettings` protocol and `build_cache_rule_set` unchanged
- `src/mcp_server/infrastructure/external_apis.py` — deleted (BL-025)
- `src/mcp_server/infrastructure/cached_llm.py` — BL-024 docstring; cache-aside on `_agenerate`; sync bypass on `_generate`; observability hooks on hit/miss

### Architecture & patterns

- `cache_config.py` imports only `domain.cache` and `typing.Protocol` — no forbidden MCP/LangChain/Supabase/`os.environ` usage.
- `cached_llm.py` implements cache-aside via domain `ICacheStore`, `CacheRuleSet`, and `build_cache_key`; LangChain imports confined to infrastructure adapter layer.
- `CachedChatModel` wiring at composition root (`wiring.build_chat_model`) unchanged; agent runtime uses `graph.ainvoke` → async `_agenerate` path, consistent with documented contract.
- Deleted placeholder removes false signal of additional third-party adapters; future adapters should follow `{provider}_adapter.py` convention per investigation.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- None.

### Warnings (should fix)

- **Uncommitted delivery.** Increment 2 changes exist only in the working tree on `testbranch` with no dedicated commit; branch diff also contains unrelated layer work. Commit infrastructure increment 2 as an isolated changeset before merge.
- **Scope creep in `cached_llm.py`.** Beyond BL-024 documentation, the diff adds `record_cache_hit` / `record_cache_miss` imports and calls. Behavior is benign and tests pass, but this functional change is not listed in INVESTIGATION2 or IMPLEMENTATION2 — either document in a follow-up changelog entry or revert if strict increment isolation is required.
- **`ARCHITECTURE.md` async-only gap.** `AGENTIC_ARCHITECTURE.md` and the class docstring state the async-only contract; `ARCHITECTURE.md` file tree still describes `cached_llm.py` generically. Consider aligning the one-line tree comment for operator discoverability.

### Suggestions (consider)

- Update `backlog/BACKLOG.md` checkboxes for BL-024/025/026 after homologation (explicitly deferred to master agent per investigation).
- `CODE_HEALTH_AUDIT1.md` still references `external_apis.py` and the empty `TYPE_CHECKING` block — refresh in a docs-only pass when convenient (also deferred per investigation).

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | pass |
| `uv run mypy src/` | pass (39 source files) |
| `uv run pytest` | pass (102 passed, 1 deprecation warning) |

## Verdict

**approve with nits**

All BL-026, BL-025, and BL-024 acceptance criteria are met: dead code removed, placeholder deleted, async-only cache contract documented accurately in code and `AGENTIC_ARCHITECTURE.md`, and quality gates pass. Layer boundaries and anti-patterns are respected. Nits are procedural (uncommitted/mixed branch diff), a small undocumented code addition (cache observability hooks), and a minor `ARCHITECTURE.md` comment gap — none block merge of the intended cleanup.
