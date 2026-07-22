# Investigation 2: Infrastructure trivial cleanup (BL-026, BL-025, BL-024)

**Date:** 2026-07-21
**Layer:** infrastructure
**Status:** approved

## User request

Batch 1 — infrastructure trivial cleanup for backlog items:

- **BL-026** — Remove empty `TYPE_CHECKING` block from `cache_config.py`
- **BL-025** — Resolve `external_apis.py` placeholder (delete; no near-term third-party adapter)
- **BL-024** — Document async-only LLM cache contract for `CachedChatModel`

## Architecture alignment

- **Layers touched:** infrastructure (code), docs (`ARCHITECTURE.md`, `AGENTIC_ARCHITECTURE.md`)
- **Patterns applied:** Dead-code removal; explicit adapter contract documentation (cache-aside on async path only)
- **Anti-patterns avoided:** No new placeholder modules; no sync cache path without callers; no backlog file edits

## Current state

| Asset | Status |
| :--- | :--- |
| `cache_config.py` lines 14–15 | Empty `if TYPE_CHECKING: pass` block; `TYPE_CHECKING` import unused after removal |
| `external_apis.py` | Docstring-only placeholder; zero Python importers (`rg` across `src/` and `tests/`) |
| `cached_llm.py` | `_agenerate` implements cache-aside; `_generate` delegates to inner with no cache |
| `AGENTIC_ARCHITECTURE.md` | File tree lists `external_apis.py`; no async-only LLM cache note |
| `ARCHITECTURE.md` | File tree lists `external_apis.py` |
| Tests | `test_llm.py` and `test_cache.py` exercise `CachedChatModel` via async `ainvoke` / `_agenerate` only |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| Dead `TYPE_CHECKING` block (BL-026) | infrastructure | high — lint noise |
| Orphan placeholder module (BL-025) | infrastructure + docs | high — false signal in architecture docs |
| Undocumented sync bypass on LLM cache (BL-024) | infrastructure + docs | medium — operator/developer confusion |

## Minimal increment

One docs-and-code cleanup slice: remove lint/dead artifacts, delete the unused placeholder file, and document that `CachedChatModel` caches only the async completion path because LangGraph/agent callers use `ainvoke`/`_agenerate`. Sync `_generate` intentionally bypasses cache until a sync caller is introduced.

### Scope (in)

- Remove `TYPE_CHECKING` block and unused import from `cache_config.py`
- Delete `external_apis.py`
- Update `ARCHITECTURE.md` and `AGENTIC_ARCHITECTURE.md` file trees (remove `external_apis.py`)
- Add async-only cache contract to `cached_llm.py` class docstring and `AGENTIC_ARCHITECTURE.md`
- Run `ruff`, `mypy`, `pytest`

### Scope (out / deferred)

- Sync `_generate` cache path (defer until sync LLM callers exist)
- Updating `backlog/BACKLOG.md` (master agent after homologation)
- Updating `CODE_HEALTH_AUDIT1.md` historical findings
- Adding first third-party adapter module (delete chosen over populate)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `src/mcp_server/infrastructure/cache_config.py` | modify | BL-026: remove dead `TYPE_CHECKING` block |
| `src/mcp_server/infrastructure/external_apis.py` | delete | BL-025: zero importers; no planned adapter |
| `src/mcp_server/infrastructure/cached_llm.py` | modify | BL-024: expand class/docstring for async-only contract |
| `ARCHITECTURE.md` | modify | Remove stale `external_apis.py` from file tree |
| `AGENTIC_ARCHITECTURE.md` | modify | Remove placeholder entry; document LLM cache async contract |

## Dependencies & environment

- Runtime deps: none
- Dev deps: none
- Secrets / env vars: none
- Commands: `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest`

## Risks & open questions

- **Risk:** Future third-party adapter needs a new file — acceptable; add `{provider}_adapter.py` per existing convention (`groq_adapter.py`, `youtube_client.py`).
- **Risk:** Sync LangChain callers could miss cache — documented explicitly; LangGraph uses async path in this codebase.

## Handoff to implementation

`IMPLEMENTATION2.md` should order: BL-026 code fix → BL-025 delete + doc tree updates → BL-024 docstring + AGENTIC_ARCHITECTURE section → verification gates.
