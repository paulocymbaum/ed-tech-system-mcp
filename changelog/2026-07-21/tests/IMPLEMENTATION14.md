# Implementation 14: LLM routing layer homologation test suite

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Test inventory:** [TEST14.md](./TEST14.md)
**Status:** done

## Summary

Map nine LLM routing catalog IDs (T-LLM13–T-LLM20, including T-LLM17b) to pytest functions delivered during application IMPLEMENTATION3. Tests use in-memory port fakes (`InMemoryGroqModelRegistry`, `NoOpDebounceGate`, `StaticGroqModelCatalog`) and minimal stub chat models — no external Groq API calls. CODE_REVIEW3 remediation items (temperature via `set_temperature`, router memoization, `token_limit_deactivation_until` wiring, sync debounce) are reflected in production code and covered by existing/extended tests.

## Checklist

- [x] **1.** T-LLM13 complexity tiers → `test_llm13_router_maps_complexity_to_model_tiers`
- [x] **2.** T-LLM14 fallback → `test_llm14_router_falls_back_on_provider_failure`
- [x] **3.** T-LLM15 token-limit deactivation → `test_llm15_token_limit_error_deactivates_model_for_three_hours`
- [x] **4.** T-LLM16 token-limit classifier → `test_llm16_is_token_limit_error_detects_context_length`
- [x] **5.** T-LLM17 async debounce → `test_llm17_debounce_gate_spaces_async_calls`
- [x] **6.** T-LLM17b sync debounce → `test_llm17b_debounce_gate_spaces_sync_calls` (CODE_REVIEW3 remediation)
- [x] **7.** T-LLM18 free-model registry → `test_llm18_groq_registry_marks_only_known_free_models_active`
- [x] **8.** T-LLM19 domain cooldown → `test_llm19_token_limit_deactivation_until_is_three_hours`
- [x] **9.** T-LLM20 wiring surface → `test_llm20_build_chat_model_returns_routing_model`
- [x] **10.** Run `uv sync --frozen`
- [x] **11.** Run `uv run ruff check src/ tests/`
- [x] **12.** Run `uv run pytest -v`
- [x] **13.** Update `HOMOLOGATION.md` with TEST14 routing coverage matrix
- [x] **14.** Set TEST14.md → approved; this file → done

## Task details

### Test modules

| Module | Catalog IDs | Action |
| :--- | :--- | :--- |
| `tests/test_llm.py` | T-LLM13–T-LLM20, T-LLM17b | existing (IMPLEMENTATION3) |

### Related coverage (outside TEST14 catalog)

| Test | Notes |
| :--- | :--- |
| `test_llm02_create_chat_model_uses_registered_groq_builder` | Temperature override via `router.set_temperature` (CODE_REVIEW3 fix) |
| `test_llm01`, `test_llm10`, `test_llm11` | Groq API key / unsupported provider / unregistered builder errors with router registered |

### Verification results

```text
uv run ruff check src/ tests/  → fail (8 pre-existing E501 in unrelated test files)
uv run pytest -v               → 178 passed, 7 skipped
uv run pytest tests/test_llm.py tests/test_llm_models.py -v → 34 passed
```

Full details in [HOMOLOGATION.md](./HOMOLOGATION.md).
