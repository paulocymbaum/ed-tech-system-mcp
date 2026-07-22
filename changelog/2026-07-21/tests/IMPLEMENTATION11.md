# Implementation 11: Domain exception taxonomy + web search deferral test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST11.md](./TEST11.md)
**Status:** done

## Summary

Map BL-009 domain exception taxonomy and BL-005 deferral to 22 pytest functions across `test_domain_exceptions.py`, `test_infrastructure_stubs.py`, and `test_interface_tools.py`. T07–T31 and remediation cases T26d/T27c/T28c were delivered during domain IMPLEMENTATION1 and CODE_REVIEW1 remediation. T26e and T27d close remaining adapter guard gaps (missing service role key, YouTube empty query).

## Checklist

- [x] **1.** Map domain hierarchy — T07 → `test_t07_domain_exception_hierarchy`
- [x] **2.** Map message preservation — T07b → `test_t07b_domain_exceptions_preserve_message`
- [x] **3.** Map raise/catch — T07c/T07d → `test_t07c_*`, `test_t07d_*`
- [x] **4.** Map invariant helpers — T07e–T07h → `test_t07e_*` through `test_t07h_*`
- [x] **5.** Map Supabase stub + guards — T26, T26b–T26d → existing tests
- [x] **6.** Add Supabase missing service role key — T26e → `test_t26e_supabase_find_documents_rejects_missing_service_role_key`
- [x] **7.** Map YouTube stub + guards — T27, T27b, T27c → existing tests
- [x] **8.** Add YouTube empty query guard — T27d → `test_t27d_youtube_search_videos_rejects_empty_query`
- [x] **9.** Map DuckDuckGo stub + guards — T28, T28b, T28c → existing tests
- [x] **10.** Map MCP error mapping — T29/T30 → `_cached_tool_invoke` integration tests
- [x] **11.** Map ToolError fallback — T31 → `test_t31_raise_as_mcp_error_maps_generic_domain_error_to_tool_error`
- [x] **12.** Run `uv sync --frozen`
- [x] **13.** Run `uv run ruff check src/ tests/`
- [x] **14.** Run `uv run mypy src/`
- [x] **15.** Run `uv run pytest -v`
- [x] **16.** Write `HOMOLOGATION.md` coverage matrix for TEST11
- [x] **17.** Set TEST11.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_domain_exceptions.py` | T07–T07h | existing (8 tests) |
| `tests/test_infrastructure_stubs.py` | T26–T28c, T26e, T27d | existing + add T26e, T27d |
| `tests/test_interface_tools.py` | T29–T31, T28-reg | existing (T28 error logging regression) |

### Verification results

```text
uv run ruff check src/ tests/  → pass
uv run mypy src/               → Success: no issues found in 44 source files
uv run pytest -v               → 139 passed
```
