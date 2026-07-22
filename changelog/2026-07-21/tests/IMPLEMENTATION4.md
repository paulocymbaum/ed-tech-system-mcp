# Implementation 4: Groq LLM integration test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST4.md](./TEST4.md)
**Status:** done

## Summary

Map existing `tests/test_llm.py` cases to TEST4 catalog IDs (LLM01–LLM08, LLM03). Add gap tests LLM09–LLM12 and C01 from CODE_REVIEW1. Extend `test_llm.py` and `test_cache.py`; no new test modules.

## Checklist

- [x] **1.** Map existing `test_llm.py` functions to LLM01–LLM08 catalog IDs
- [x] **2.** Map `test_l03_available_language_models_include_openai_anthropic_and_groq` to L03
- [x] **3.** Implement LLM09 (unknown model id raises)
- [x] **4.** Implement LLM10 (unsupported provider raises)
- [x] **5.** Implement LLM11 (unregistered builder raises)
- [x] **6.** Implement LLM12 (`DEFAULT_WORKFLOW_EXECUTION_CONFIG` matches `config.json`)
- [x] **7.** Implement C20 (`LLM_COMPLETION` default cache rule)
- [x] **8.** Run `uv run ruff check src/ tests/`
- [x] **9.** Run `uv run mypy src/`
- [x] **10.** Run `uv run pytest -v`
- [x] **11.** Write `HOMOLOGATION.md` coverage matrix for TEST4
- [x] **12.** Set TEST4.md → approved, this file → done

## Task details

### 3–7. New gap tests

LLM09–LLM11 exercise `resolve_language_model` and `create_chat_model` error paths from public contracts. LLM12 reads committed `config.json` and compares to `DEFAULT_WORKFLOW_EXECUTION_CONFIG`. C01 asserts domain default rule fields for `LLM_COMPLETION`.

### Verification

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest -v
```
