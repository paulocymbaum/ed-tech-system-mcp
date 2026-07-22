# Test Inventory 3: Operational config.json and language model registry

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [entrypoint/INVESTIGATION2.md](../entrypoint/INVESTIGATION2.md), [entrypoint/IMPLEMENTATION2.md](../entrypoint/IMPLEMENTATION2.md), [entrypoint/CODE_REVIEW2.md](../entrypoint/CODE_REVIEW2.md)

## Scope

Validate the operational config increment across entrypoint and application layers:

- Repo-root `config.json` with `node_retries`, `workflow_timeout`, `agent_node_timeout`
- Pydantic `OperationalConfig` loader (`operational_config.py`)
- Application `WorkflowExecutionConfig` runtime accessor (`workflow_config.py`)
- Composition-root mapping and initialization (`wiring.py`)
- `main()` bootstrap order (operational config before MCP server)
- `AVAILABLE_LANGUAGE_MODELS` registry (`llm_models.py`)

Existing coverage: `tests/test_operational_config.py` (6 tests), `tests/test_llm_models.py` (4 tests), `tests/test_entrypoint.py` (`test_main_startup_loads_operational_config_before_mcp_server`). This inventory maps those cases to catalog IDs and adds gaps from CODE_REVIEW2.

## Test catalog

### Entrypoint — `OperationalConfig` loader (happy path)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| O01 | `test_o01_load_operational_config_from_repo_root` | `config.json` committed values | `load_operational_config()` default path | `node_retries==3`, `workflow_timeout==300`, `agent_node_timeout==60` | Read expected values from committed `config.json` |
| O02 | `test_o02_load_operational_config_from_custom_path` | `load_operational_config(path)` | tmp `config.json` with custom values | Parsed model matches JSON fields (incl. float timeout) | Write JSON to tmp path; assert field equality |
| O08 | `test_o08_operational_config_allows_zero_retries` | `Field(ge=0)` on `node_retries` | `OperationalConfig(node_retries=0, …)` | No validation error; `node_retries==0` | Construct model directly; assert field value |

### Entrypoint — `OperationalConfig` loader (error treatment)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| O03 | `test_o03_operational_config_rejects_non_positive_timeouts` | `Field(gt=0)` on timeout fields | `workflow_timeout=0` or `agent_node_timeout=-1` | `ValidationError` | `pytest.raises(ValidationError)` |
| O04 | `test_o04_operational_config_rejects_negative_retries` | `Field(ge=0)` on `node_retries` | `node_retries=-1` | `ValidationError` | `pytest.raises(ValidationError)` |
| O11 | `test_o11_load_operational_config_missing_file_raises` | `Path.read_text` on missing path | Non-existent tmp path | `FileNotFoundError` | `pytest.raises(FileNotFoundError)` |
| O12 | `test_o12_load_operational_config_missing_keys_raises` | Pydantic required fields | JSON `{}` in tmp file | `ValidationError` | `pytest.raises(ValidationError)` |

### Entrypoint — path resolution

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| O10 | `test_o10_default_config_path_points_to_repo_root_config` | `default_config_path()` docstring | Call `default_config_path()` | Path ends with `config.json` and file exists | Assert suffix and `is_file()` |

### Application — `WorkflowExecutionConfig` runtime accessor

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| O05 | `test_o05_initialize_application_runtime_sets_workflow_config` | `initialize_application_runtime` | `OperationalConfig` instance | Returned config equals `build_workflow_execution_config`; getter returns same | Assert equality on dataclass instances |
| O06 | `test_o06_get_workflow_execution_config_requires_initialization` | `get_workflow_execution_config` guard | No prior `set_` / `initialize_` | `RuntimeError` with "not been initialized" | `pytest.raises(RuntimeError, match=…)` |
| O09 | `test_o09_build_workflow_execution_config_maps_field_names` | `build_workflow_execution_config` mapping | Known `OperationalConfig` | `workflow_timeout_seconds` and `agent_node_timeout_seconds` match operational float fields | Assert mapped attribute names and values |

### Entrypoint — `main()` bootstrap order

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| E01 | `test_e01_main_startup_loads_operational_config_before_mcp_server` | `main()` sequence in `main.py` | Mock bootstrap, settings, loader, runtime init, server | Call order: bootstrap → settings → operational config → runtime init → create server | Track call order list; assert `server.run()` once |

### Application — `AVAILABLE_LANGUAGE_MODELS` registry

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| L01 | `test_l01_available_language_models_is_non_empty` | registry non-empty contract | Import `AVAILABLE_LANGUAGE_MODELS` | `len > 0` | Assert length |
| L02 | `test_l02_available_language_models_have_required_fields` | `LanguageModelSpec` TypedDict | Iterate registry | Each entry has non-empty `id`, `provider`, `display_name` | Assert key subset and truthy values |
| L03 | `test_l03_available_language_models_include_openai_and_anthropic` | investigation scope | Registry providers set | Contains `openai` and `anthropic` | Assert provider membership |
| L04 | `test_l04_language_model_spec_typing` | `LanguageModelSpec` fields | First registry entry | `id` is `str` | `isinstance` on typed sample |
| L05 | `test_l05_available_language_models_have_unique_ids` | CODE_REVIEW2 nit — duplicate ids | Collect all `id` values | No duplicates | Assert `len(ids) == len(set(ids))` |

## Deferred (not testable yet)

- LangGraph node retry/timeout enforcement inside graph compilation
- `application/llm.py` factory consuming `AVAILABLE_LANGUAGE_MODELS`
- Env/Doppler overrides for operational values
- `get_workflow_execution_config()` consumption by `agent.py`
- Invalid JSON syntax (`JSONDecodeError`) — low value; Pydantic/missing-key path covers startup failure

## Handoff to implementation

[IMPLEMENTATION3.md](./IMPLEMENTATION3.md)
