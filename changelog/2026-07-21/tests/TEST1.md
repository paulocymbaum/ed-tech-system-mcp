# Test Inventory 1: Scaffold business rules and data contracts

**Date:** 2026-07-21
**Layer:** tests (cross-cutting)
**Status:** approved
**References:** [entrypoint/INVESTIGATION1.md](../entrypoint/INVESTIGATION1.md)

## Scope

Post-scaffold validation of every implemented contract in `src/mcp_server/`:

- Domain entities (`VideoResult`, `DocumentHit`) and exceptions
- Interface validation schemas (`VideoSearchRequest`, `VideoSearchResponse`)
- Application workflow (`DocumentVideoWorkflow.retrieve_with_videos`)
- Interface MCP tool (`health_check`)
- Entrypoint bootstrap and `Settings`
- Infrastructure adapter stubs (`NotImplementedError` contract)

Infrastructure adapters are intentionally unimplemented; tests assert the deferred contract only.

## Test catalog

### Domain — `VideoResult`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T01 | `test_t01_video_result_happy_path` | `domain/schemas.py` required fields | Valid title, channel, url | Model instantiates; fields equal inputs | Assert public attributes match constructor args |
| T02 | `test_t02_video_result_default_relevance_score` | `relevance_score` default `0.0` | Omit relevance_score | `relevance_score == 0.0` | Read default from Field definition, not hard-coded magic beyond spec |
| T03 | `test_t03_video_result_relevance_score_bounds` | `ge=0.0, le=1.0` | score `-0.1` and `1.1` | `ValidationError` raised | `pytest.raises(ValidationError)`; no custom error messages |
| T04 | `test_t04_video_result_optional_duration` | `duration_seconds: int \| None = None` | Omit duration | `duration_seconds is None` | Assert optional field absent |

### Domain — `DocumentHit`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T05 | `test_t05_document_hit_happy_path` | required id, title, content | Valid strings | Model instantiates | Assert attributes |
| T06 | `test_t06_document_hit_metadata_defaults_empty` | `metadata` default_factory=dict | Omit metadata | `metadata == {}` | Assert empty dict, not None |

### Domain — exceptions

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T07 | `test_t07_domain_exception_hierarchy` | `exceptions.py` inheritance | Instantiate each class | `ResourceNotFoundError` and `ValidationError` are `DomainError` subclasses | `isinstance` checks only |

### Interface validation — `VideoSearchRequest`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T08 | `test_t08_video_search_request_happy_path` | all fields valid | query, max_results, language, safe_search | Model instantiates with given values | Assert each field |
| T09 | `test_t09_video_search_request_defaults` | Field defaults in validation.py | Only `query` provided | max_results=5, language="en", safe_search=True | Compare to schema defaults |
| T10 | `test_t10_video_search_request_empty_query` | `query` min_length=1 | `query=""` | `ValidationError` | pydantic raises |
| T11 | `test_t11_video_search_request_max_results_bounds` | `ge=1, le=25` | max_results 0 and 26 | `ValidationError` | boundary values from Field |
| T12 | `test_t12_video_search_request_language_length` | `min_length=2, max_length=10` | `"a"` and 11-char string | `ValidationError` | boundary from Field |

### Interface validation — `VideoSearchResponse`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T13 | `test_t13_video_search_response_happy_path` | `videos: list[VideoResult]` | List of valid VideoResult dicts | Model instantiates; len matches | Assert list length and nested types |
| T14 | `test_t14_video_search_response_empty_list` | list type allows empty | `videos=[]` | Valid empty response | Assert `videos == []` |

### Application — `DocumentVideoWorkflow`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T15 | `test_t15_workflow_uses_first_document_title_for_video_search` | workflow docstring + lines 27-28 | Fake repo returns one doc; fake video client records query | Video client receives `documents[0].title`, not raw query | Fake port records `last_query`; assert against doc title from fake data |
| T16 | `test_t16_workflow_falls_back_to_query_when_no_documents` | lines 26-28 else branch | Fake repo returns `[]` | Video client receives original query | Fake port records query |
| T17 | `test_t17_workflow_routes_document_limit` | `find_documents(query, limit=document_limit)` | document_limit=3 | Repo receives limit=3 | Fake repo records `last_limit` |
| T18 | `test_t18_workflow_routes_video_limit` | `search_videos(..., max_results=video_limit)` | video_limit=2 | Video client receives max_results=2 | Fake client records `last_max_results` |
| T19 | `test_t19_workflow_returns_documents_and_videos_tuple` | return type annotation | Fakes return known lists | Tuple of (documents, videos) with fake outputs | Assert lengths and identity of fake returns |

### Interface — `health_check` tool

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T20 | `test_t20_health_check_returns_ok` | docstring + return type `str` | Call `health_check()` | Returns `"ok"` | Assert return value equals literal from source |

### Entrypoint — `bootstrap_environment`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T21 | `test_t21_bootstrap_skips_dotenv_outside_development` | `APP_ENV != "development"` guard | monkeypatch APP_ENV=production | `load_dotenv` not called | Patch `dotenv.load_dotenv`; assert not called |
| T22 | `test_t22_bootstrap_loads_dotenv_in_development` | development branch | monkeypatch APP_ENV=development | `load_dotenv` called once with override=False | Assert call kwargs from source |

### Entrypoint — `Settings`

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T23 | `test_t23_settings_requires_supabase_credentials` | required Field aliases | Missing SUPABASE_URL | `ValidationError` on Settings() | pydantic raises |
| T24 | `test_t24_settings_loads_with_required_env` | Field aliases | Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY | Settings instantiates; values match env | monkeypatch env; assert public fields |
| T25 | `test_t25_settings_youtube_key_optional` | `youtube_api_key` default None | Omit YOUTUBE_API_KEY | `youtube_api_key is None` | Assert optional SecretStr field |

### Infrastructure — deferred adapters

| ID | Test name | Contract source | Input / setup | Expected behavior | Bias-free validation method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T26 | `test_t26_supabase_find_documents_not_implemented` | stub raises NotImplementedError | Instantiate with dummy creds; await find_documents | `NotImplementedError` | pytest.raises on await |
| T27 | `test_t27_youtube_search_videos_not_implemented` | stub | Instantiate; await search_videos | `NotImplementedError` | pytest.raises |
| T28 | `test_t28_duckduckgo_search_not_implemented` | stub | Instantiate; await search | `NotImplementedError` | pytest.raises |

## Deferred (not testable yet)

- LangChain agent/graph behavior (`create_agent` placeholder)
- Real MCP tool registration beyond `health_check`
- Integration tests against Supabase, YouTube, DuckDuckGo APIs
- `main()` full server startup (requires transport; out of unit scope)
- `load_settings()` when called from `main()` with missing env (covered by T23)

## Handoff to implementation

See [IMPLEMENTATION1.md](./IMPLEMENTATION1.md) for ordered test file tasks and verification gates.
