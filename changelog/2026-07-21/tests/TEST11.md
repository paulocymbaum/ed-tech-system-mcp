# Test Inventory 11: Domain exception taxonomy + web search deferral (BL-009, BL-005)

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [domain/INVESTIGATION1.md](../domain/INVESTIGATION1.md), [domain/IMPLEMENTATION1.md](../domain/IMPLEMENTATION1.md), [domain/CODE_REVIEW1.md](../domain/CODE_REVIEW1.md)

## Scope

Homologate domain increment 1 — Batch 5:

- **BL-009** — Activate domain exception taxonomy: rename `ValidationError` → `DomainValidationError`; pure `domain/invariants.py` guards; infrastructure adapters raise domain errors before stub `NotImplementedError`; `interface/error_mapping.py` maps `DomainError` subclasses to MCP protocol errors in `_cached_tool_invoke`.
- **BL-005** — Web search wiring deferred: `# deferred — web search` comment on `build_search_client()` in `wiring.py`; documented in `AGENTIC_ARCHITECTURE.md` (no runtime behavior to test).

Layers touched: domain (primary), infrastructure, interface. Prior inventories TEST1–TEST10 remain valid.

## Test catalog

### domain/exceptions — hierarchy and messages

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T07 | `test_t07_domain_exception_hierarchy` | `exceptions.py` class hierarchy | Instantiate `ResourceNotFoundError`, `DomainValidationError` | Both are `isinstance(..., DomainError)` | `isinstance` on public exception types |
| T07b | `test_t07b_domain_exceptions_preserve_message` | `Exception` message contract | Construct with string args | `str(exc)` equals message | Assert `str()` on constructed instances |
| T07c | `test_t07c_resource_not_found_raise_and_catch` | `ResourceNotFoundError` docstring | Raise with message | Catchable as `ResourceNotFoundError` with match | `pytest.raises` with match |
| T07d | `test_t07d_domain_validation_raise_and_catch` | `DomainValidationError` docstring; Pydantic collision avoidance | Raise with message | Catchable as `DomainValidationError` with match | `pytest.raises` with match |

### domain/invariants — pure guard helpers

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T07e | `test_t07e_require_non_empty_text_rejects_blank` | `require_non_empty_text` docstring | Whitespace-only string | Raises `DomainValidationError` with `{field} must not be empty` | Message derived from `field` param |
| T07f | `test_t07f_require_non_empty_text_returns_stripped_value` | Return contract | `"  plants  "` | Returns `"plants"` | Assert return value |
| T07g | `test_t07g_require_positive_int_rejects_non_positive` | `require_positive_int` docstring | `value=0` | Raises `DomainValidationError` with `{field} must be positive, got {value}` | Message from field name and input |
| T07h | `test_t07h_require_credential_raises_resource_not_found` | `require_credential` docstring | Empty credential string | Raises `ResourceNotFoundError` with `{resource} credentials are not configured` | Message from `resource` param |

### SupabaseRepository — adapter guards (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T26 | `test_t26_supabase_find_documents_not_implemented` | Stub contract (BL-022 deferred) | Valid url, key, query | Raises `NotImplementedError` after guards pass | `pytest.raises(NotImplementedError)` |
| T26b | `test_t26b_supabase_find_documents_rejects_empty_query` | `require_non_empty_text` via adapter | Whitespace query | `DomainValidationError` before stub | Match `query must not be empty` |
| T26c | `test_t26c_supabase_find_documents_rejects_missing_credentials` | `require_credential` on url | Empty `supabase_url` | `ResourceNotFoundError` for Supabase | Match credential message |
| T26d | `test_t26d_supabase_find_documents_rejects_non_positive_limit` | `require_positive_int` via adapter | `limit=0` | `DomainValidationError` before stub | Match `limit must be positive` |
| T26e | `test_t26e_supabase_find_documents_rejects_missing_service_role_key` | `require_credential` on key | Empty `service_role_key` | `ResourceNotFoundError` for Supabase | Match credential message |

### YouTubeDataApiClient — adapter guards (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T27 | `test_t27_youtube_search_videos_not_implemented` | Stub contract (BL-022 deferred) | Valid api key, query | Raises `NotImplementedError` after guards | `pytest.raises(NotImplementedError)` |
| T27b | `test_t27b_youtube_search_videos_rejects_missing_api_key` | `require_credential` | Empty api key | `ResourceNotFoundError` for YouTube API | Match credential message |
| T27c | `test_t27c_youtube_search_videos_rejects_non_positive_max_results` | `require_positive_int` via adapter | `max_results=0` | `DomainValidationError` before stub | Match `max_results must be positive` |
| T27d | `test_t27d_youtube_search_videos_rejects_empty_query` | `require_non_empty_text` via adapter | Whitespace query | `DomainValidationError` before stub | Match `query must not be empty` |

### DuckDuckGoSearchClient — adapter guards (infrastructure)

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T28 | `test_t28_duckduckgo_search_not_implemented` | Stub contract (BL-022 deferred) | Valid query | Raises `NotImplementedError` after guards | `pytest.raises(NotImplementedError)` |
| T28b | `test_t28b_duckduckgo_search_rejects_empty_query` | `require_non_empty_text` via adapter | Empty query | `DomainValidationError` before stub | Match `query must not be empty` |
| T28c | `test_t28c_duckduckgo_search_rejects_non_positive_max_results` | `require_positive_int` via adapter | `max_results=0` | `DomainValidationError` before stub | Match `max_results must be positive` |

### interface/error_mapping + _cached_tool_invoke — MCP boundary

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T29 | `test_t29_cached_tool_invoke_maps_resource_not_found_to_fastmcp_error` | IMPLEMENTATION1 task 6 | Invoker raises `ResourceNotFoundError` | `_cached_tool_invoke` raises `fastmcp.NotFoundError` | `pytest.raises(FastMcpNotFoundError)` with message |
| T30 | `test_t30_cached_tool_invoke_maps_domain_validation_to_mcp_error` | IMPLEMENTATION1 task 6 | Invoker raises `DomainValidationError` | `_cached_tool_invoke` raises `mcp.McpError` code -32602 | `pytest.raises(McpError)` with `Invalid params:` prefix |
| T31 | `test_t31_raise_as_mcp_error_maps_generic_domain_error_to_tool_error` | `raise_as_mcp_error` fallback branch | Minimal `DomainError` subclass | Raises `fastmcp.ToolError` with message | Direct call to `raise_as_mcp_error` |
| T28-reg | `test_t28_cached_tool_invoke_logs_error_outcome` | Non-domain errors unchanged | Invoker raises `ValueError` | Re-raises `ValueError`; logs `outcome=error` | Existing regression; not domain-mapped |

## Deferred (not testable yet)

- **BL-022 HTTP adapter implementation** — stubs keep `NotImplementedError` after guards; no live Supabase/YouTube/DuckDuckGo calls
- **BL-006 `search_web` MCP tool** — not registered
- **`ISearchClient` injection into `DocumentVideoWorkflow` or LangGraph** — BL-005 explicitly deferred
- **`build_search_client()` production wiring** — factory exists with `# deferred — web search` comment only; verify via doc/changelog, not pytest
- **Empty search result → `ResourceNotFoundError`** — explicitly out of scope per INVESTIGATION1 (empty lists are valid success)
- **`backlog/BACKLOG.md` BL-009/BL-005 checkbox updates** — master agent hygiene

## Handoff to implementation

[IMPLEMENTATION11.md](./IMPLEMENTATION11.md)
