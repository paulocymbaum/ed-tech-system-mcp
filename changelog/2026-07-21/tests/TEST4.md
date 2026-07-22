# Test Inventory 4: Groq LLM integration, caching, and workflow limits

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [application/INVESTIGATION1.md](../application/INVESTIGATION1.md), [application/IMPLEMENTATION1.md](../application/IMPLEMENTATION1.md), [application/CODE_REVIEW1.md](../application/CODE_REVIEW1.md)

## Scope

Validate the Groq LLM increment across application, entrypoint, infrastructure, and domain layers:

- `create_chat_model()` factory with Groq builder injection (`application/llm.py`)
- `AVAILABLE_LANGUAGE_MODELS` Groq entries and `resolve_language_model()` (`llm_models.py`)
- LangGraph retry/timeout policies from `WorkflowExecutionConfig` (`agent.py`)
- `CachedChatModel` cache-aside on async completions (`infrastructure/cached_llm.py`)
- `LLM_COMPLETION` cache operation defaults (`domain/cache.py`)
- Wiring via `build_chat_model()` and `initialize_application_runtime(settings)` (`wiring.py`, `main.py`)
- Settings fields: `GROQ_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`, LLM cache TTL/prefix

Existing coverage: `tests/test_llm.py` (8 tests), updated `tests/test_llm_models.py` (`test_l03` includes Groq). This inventory maps those cases to catalog IDs and adds gaps from CODE_REVIEW1.

## Test catalog

### Application — LLM factory

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM01 | `test_llm01_create_chat_model_requires_groq_api_key` | `create_chat_model` guard | Settings without `GROQ_API_KEY` | `ValueError` mentioning `GROQ_API_KEY` | `pytest.raises(ValueError, match=…)` |
| LLM02 | `test_llm02_create_chat_model_uses_registered_groq_builder` | builder injection | Stub builder + `GROQ_API_KEY` set | Returns model from registered builder | `isinstance` on stub type |
| LLM10 | `test_llm10_create_chat_model_unsupported_provider_raises` | deferred OpenAI path | `model_id="gpt-4o"` with Groq key set | `ValueError` for unsupported provider | `pytest.raises(ValueError, match=…)` |
| LLM11 | `test_llm11_create_chat_model_unregistered_builder_raises` | `register_groq_model_builder` guard | No builder registered; key set | `RuntimeError` | `pytest.raises(RuntimeError, match=…)` |

### Application — model registry

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM03 | `test_llm03_resolve_language_model_returns_groq_spec` | `resolve_language_model` | Known Groq model id | `provider == "groq"` | Assert field on returned spec |
| LLM09 | `test_llm09_resolve_language_model_unknown_id_raises` | `resolve_language_model` | Unknown id | `ValueError` | `pytest.raises(ValueError, match=…)` |
| L03 | `test_l03_available_language_models_include_openai_anthropic_and_groq` | registry providers | Import registry | Contains `groq`, `openai`, `anthropic` | Assert provider membership |

### Infrastructure — cached LLM

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM04 | `test_llm04_cached_chat_model_hits_cache_on_second_ainvoke` | cache-aside on `_agenerate` | In-memory cache + enabled rule | Second `ainvoke` hits cache; inner called once | Assert call counts on stub and cache |

### Application — LangGraph policies

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM05 | `test_llm05_agent_nodes_use_workflow_execution_config` | `RetryPolicy`, timeout helpers | `WorkflowExecutionConfig` set | `max_attempts = node_retries + 1`; timeouts match config | Assert policy fields and helper return values |
| LLM12 | `test_llm12_default_workflow_execution_config_matches_config_json` | `DEFAULT_WORKFLOW_EXECUTION_CONFIG` | Import constant | Matches committed `config.json` values | Read `config.json` and assert field equality |

### Entrypoint — wiring and startup

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| LLM06 | `test_llm06_initialize_application_runtime_wires_chat_model` | `initialize_application_runtime(operational, settings)` | Operational + settings with Groq key | `get_chat_model()` non-None | Assert runtime accessor |
| LLM07 | `test_llm07_build_chat_model_wraps_with_cache_when_enabled` | `build_chat_model` | `CACHE_ENABLED=true` | Returns `CachedChatModel` | Assert type name |
| LLM08 | `test_llm08_set_chat_model_runtime_accessor` | `set_chat_model` / `get_chat_model` | Stub model | Round-trip returns same instance | Identity assertion |

### Domain — LLM cache defaults

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C20 | `test_c20_llm_completion_default_cache_rule` | `DEFAULT_CACHE_RULES` | Import `CacheOperationType.LLM_COMPLETION` rule | `ttl_seconds==3600`, `key_prefix=="llm"` | Assert rule fields from domain contract |

## Deferred (not testable yet)

- OpenAI/Anthropic `create_chat_model` implementations
- Graph nodes invoking `get_chat_model()` for reasoning
- SQL agent graph with LLM
- LangChain `@tool` wrappers
- Env/Doppler overrides for operational `config.json` values
- Sync `_generate` path caching in `CachedChatModel`

## Handoff to implementation

[IMPLEMENTATION4.md](./IMPLEMENTATION4.md)
