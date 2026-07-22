# Test Inventory 14: LLM routing layer (application IMPLEMENTATION3)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [../application/INVESTIGATION3.md](../application/INVESTIGATION3.md), [../application/IMPLEMENTATION3.md](../application/IMPLEMENTATION3.md), [../application/CODE_REVIEW3.md](../application/CODE_REVIEW3.md)

## Scope

Homologate the LLM routing layer delivered in application IMPLEMENTATION3: complexity-based model selection (levels 1–3), failure fallback, debounce gate (sync + async), dynamic Groq registry with free-model defaults, 3-hour token-limit deactivation, and composition-root wiring through `RoutingChatModel`. Tests live in `tests/test_llm.py` (`test_llm13`–`test_llm20`, `test_llm17b`). Prior inventories TEST1–TEST13 remain valid.

| Component | Layer | Contract source |
| :--- | :--- | :--- |
| `LLMRouter` | application | `candidate_model_ids`, `generate`, `agenerate`; INVESTIGATION3 |
| `is_token_limit_error` | application | `llm_router.py` classifier heuristics |
| `token_limit_deactivation_until` | domain | `TOKEN_LIMIT_DEACTIVATION_HOURS = 3` |
| `GroqModelRegistry` | infrastructure | `KNOWN_FREE_GROQ_MODEL_IDS`; active flag defaults |
| `IntervalLLMDebounceGate` | infrastructure | `ILLMDebounceGate.acquire` / `acquire_sync` |
| `build_chat_model` / wiring | entrypoint | No direct `ChatGroq` bypass; `RoutingChatModel` surface |

## Test catalog

### LLMRouter — complexity mapping (happy path)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM13 | `test_llm13_router_maps_complexity_to_model_tiers` | `LLMRouter.candidate_model_ids`; `model_capability_score` tier indices | In-memory registry with 3 models ranked low→high capability | LOW → lowest-capability id; MEDIUM → mid index; HIGH → highest-capability id | Assert first element of each chain against capability ordering, not implementation details |

### LLMRouter — failure fallback (happy path)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM14 | `test_llm14_router_falls_back_on_provider_failure` | `LLMRouter.generate` fallback loop | Primary model raises `RuntimeError`; secondary succeeds | Response content equals fallback model id | Fake builder returns model id as content; no mock on router internals |

### LLMRouter — token-limit deactivation (error treatment)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM15 | `test_llm15_token_limit_error_deactivates_model_for_three_hours` | `generate` + `registry.deactivate_until(token_limit_deactivation_until())` | Model raises `context_length_exceeded` | Model deactivated; `deactivated_until` ≥ now + 3 h (±5 s) | Registry record `active=False`; deadline from domain policy |
| T-LLM16 | `test_llm16_is_token_limit_error_detects_context_length` | `is_token_limit_error` heuristics | `context_length_exceeded` vs unrelated error | True for token-limit message; False for network timeout | Public classifier only; no registry/router |

### IntervalLLMDebounceGate — spacing (edge cases)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM17 | `test_llm17_debounce_gate_spaces_async_calls` | `ILLMDebounceGate.acquire` | Interval 0.05 s; two consecutive `acquire()` | Elapsed ≥ 0.04 s | Monotonic clock; no router involvement |
| T-LLM17b | `test_llm17b_debounce_gate_spaces_sync_calls` | `ILLMDebounceGate.acquire_sync`; CODE_REVIEW3 remediation | Interval 0.05 s; two consecutive `acquire_sync()` | Elapsed ≥ 0.04 s | Sync path used by `LLMRouter.generate` |

### GroqModelRegistry — free-model defaults (parameter routing)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM18 | `test_llm18_groq_registry_marks_only_known_free_models_active` | `KNOWN_FREE_GROQ_MODEL_IDS`; `_record_from_catalog_entry` | Static catalog: known-free id + unknown paid id | Free model `active=True`; non-free `active=False` | Assert `GroqModelRecord.active` from allowlist, not HTTP |

### Domain cooldown helper — policy (happy path)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM19 | `test_llm19_token_limit_deactivation_until_is_three_hours` | `token_limit_deactivation_until`; `TOKEN_LIMIT_DEACTIVATION_HOURS` | Fixed `now` datetime | Returns `now + timedelta(hours=3)` | Domain constant; router uses same helper per CODE_REVIEW3 remediation |

### Wiring — composition root (happy path)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T-LLM20 | `test_llm20_build_chat_model_returns_routing_model` | `build_chat_model` → `create_chat_model` → `RoutingChatModel` | Env + patched catalog; `CACHE_ENABLED=false` | Returned model is `RoutingChatModel` instance | `isinstance` on public builder output; no `ChatGroq` type check |

## Deferred (not testable yet)

- **OpenAI/Anthropic routing** — static registry only; deferred per INVESTIGATION3
- **Redis-backed Groq registry persistence** — in-process registry only
- **Live Groq `/v1/models` HTTP integration** — catalog client uses fakes/monkeypatch in unit tests
- **Paid model activation policy** — beyond default-inactive flag; deferred
- **Router memoization across multiple `build_chat_model` calls** — wiring behavior; no dedicated contract test (acceptable; test_llm20 covers single-build path)

## Handoff to implementation

[IMPLEMENTATION14.md](./IMPLEMENTATION14.md)
