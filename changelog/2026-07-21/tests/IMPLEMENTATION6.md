# Implementation 6: Application orchestration and MCP tools test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST6.md](./TEST6.md)
**Status:** done

## Summary

Homologated BL-001, BL-010, BL-011, BL-006, and BL-013 by mapping existing implementation tests to TEST6 catalog IDs and adding five gap tests from CODE_REVIEW1/2 suggestions.

## Checklist

- [x] **1.** Map BL-001 — LLM05b graph delegation; UI01 local UI metadata
- [x] **2.** Map BL-010 — T15–T19d parallel/sequential branches (`test_workflows.py`)
- [x] **3.** Map BL-011 — LLM05 retry tiers; LLM05c direct timeout
- [x] **4.** Map BL-006 — T22–T24 MCP tools; T08–T14 video validation
- [x] **5.** Map BL-013 — T15 snippet pruning; T23 find_documents pruning
- [x] **6.** Add LLM05d — graph delegation nodes, no skeleton `_count_*`
- [x] **7.** Add T25 — `run_workflow` pruned document payload
- [x] **8.** Add T26 — `run_workflow` workflow timeout enforcement
- [x] **9.** Add T16 — `DocumentQueryRequest` validation
- [x] **10.** Add T17 — `WorkflowRunRequest` validation
- [x] **11.** Run `uv run ruff check src/ tests/`
- [x] **12.** Run `uv run mypy src/`
- [x] **13.** Run `uv run pytest -v`
- [x] **14.** Write `HOMOLOGATION.md` coverage matrix for TEST6
- [x] **15.** Set TEST6.md → approved, this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_workflows.py` | T15–T19d | mapped existing |
| `tests/test_llm.py` | LLM05, LLM05b, LLM05c, LLM05d | added LLM05d |
| `tests/test_interface_tools.py` | T22–T26 | added T25, T26 |
| `tests/test_validation.py` | T08–T17 | added T16, T17 |
| `tests/interface/test_local_ui_api.py` | UI01 | mapped existing |

### Verification

```bash
uv sync --frozen
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest -v
```
