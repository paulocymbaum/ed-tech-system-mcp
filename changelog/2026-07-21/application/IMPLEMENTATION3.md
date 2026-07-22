# Implementation 3: LLM routing layer

**Date:** 2026-07-21
**Layer:** application
**Investigation:** [INVESTIGATION3.md](./INVESTIGATION3.md)
**Status:** done

## Summary

Introduce domain routing ports, infrastructure catalog/registry/debounce adapters, and an application `LLMRouter` with `RoutingChatModel` so all Groq completions flow through complexity-based selection, debounce, fallback, and token-limit deactivation.

## Checklist

- [x] **1.** Create `domain/llm_routing.py` — types and ports
- [x] **2.** Create `infrastructure/groq_model_catalog.py` — Groq models API client
- [x] **3.** Create `infrastructure/groq_model_registry.py` — in-memory registry with 3 h deactivation
- [x] **4.** Create `infrastructure/llm_debounce.py` — debounce gate
- [x] **5.** Create `application/llm_router.py` — complexity mapping and fallback
- [x] **6.** Create `application/routing_chat_model.py` — LangChain adapter
- [x] **7.** Update `application/llm.py` — route Groq through router
- [x] **8.** Update `settings.py` — router defaults
- [x] **9.** Update `wiring.py` — wire router at composition root
- [x] **10.** Extend `tests/test_llm.py` — routing contracts
- [x] **11.** Update `changelog/2026-07-21/tests/HOMOLOGATION.md`
- [x] **12.** Run `uv run ruff check src/` and fix issues
- [x] **13.** Run `uv run mypy src/` and fix issues
- [x] **14.** Run `uv run pytest tests/test_llm.py tests/test_llm_models.py`
- [x] **15.** Update investigation/implementation status

## Task details

### 1. Domain ports

- **File(s):** `src/mcp_server/domain/llm_routing.py`
- **Done when:** `LLMComplexity`, `GroqModelRecord`, `IGroqModelCatalogClient`, `IGroqModelRegistry`, `ILLMDebounceGate` defined without framework imports

### 5. Application router

- **File(s):** `src/mcp_server/application/llm_router.py`
- **Done when:** Complexity 1/2/3 selects tier-appropriate active models; failures walk fallback chain; token-limit errors deactivate model 3 h

### 9. Wiring

- **File(s):** `src/mcp_server/wiring.py`
- **Done when:** `build_chat_model` constructs router; no direct `build_groq_chat_model` in `create_chat_model` path

## Completion criteria

- [x] All checklist items checked
- [x] No secrets committed; `.env` unchanged unless user requested
- [x] Changes match ARCHITECTURE.md layer rules
