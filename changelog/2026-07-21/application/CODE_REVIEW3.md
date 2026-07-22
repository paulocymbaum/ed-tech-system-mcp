# Code Review 3: LLM routing layer (complexity, fallback, debounce, dynamic Groq registry)

**Date:** 2026-07-21
**Layer:** application
**Branch:** develop
**Base:** develop HEAD (`466127a` — no LLM-routing commits; review covers working tree)
**Status:** final

## Changelog references

- [INVESTIGATION3.md](./INVESTIGATION3.md)
- [IMPLEMENTATION3.md](./IMPLEMENTATION3.md)

## Commits reviewed

| SHA | Message |
| :--- | :--- |
| `466127a` | Add test for scan_secrets to skip deleted staged files |
| `27c79a3` | Enhance secret scanning script to exclude deleted/renamed files… |
| `20d1bdc` | Merge branch 'testbranch' |
| `c6d1a8a` | SetUp |

**Working tree (uncommitted / untracked):** All IMPLEMENTATION3 deliverables — new domain ports (`llm_routing.py`), application router (`llm_router.py`, `routing_chat_model.py`), infrastructure adapters (`groq_model_catalog.py`, `groq_model_registry.py`, `llm_debounce.py`), modified `llm.py` / `settings.py` / `wiring.py`, extended `tests/test_llm.py` (`test_llm13`–`test_llm20`), changelog `INVESTIGATION3.md` / `IMPLEMENTATION3.md`, and `HOMOLOGATION.md` routing section.

## Summary

IMPLEMENTATION3 is **delivered in the working tree** and aligns with INVESTIGATION3 scope: domain routing ports, infrastructure catalog/registry/debounce adapters, application `LLMRouter` with complexity tiers and fallback, `RoutingChatModel` as the sole Groq execution surface, composition-root wiring via `build_llm_router()`, and eight new routing contract tests. Clean Architecture import contracts pass; mypy and the LLM pytest slice pass. Verdict is **request changes** because core routing files and changelog artifacts are **uncommitted**, `ruff format --check` fails on two files, and `create_chat_model(..., temperature=...)` no longer applies per-call temperature overrides.

## Documentation alignment

| Source | Finding |
| :--- | :--- |
| INVESTIGATION3 | All scope (in) items present in working tree. Scope (out) respected — OpenAI/Anthropic static registry, Redis persistence, and `config.json` debounce keys deferred. |
| IMPLEMENTATION3 | Checklist complete; status `done` matches working-tree code. |
| ARCHITECTURE.md | Layer boundaries respected in code. **Drift:** file map under `src/mcp_server/` does not list `domain/llm_routing.py`, `application/llm_router.py`, `routing_chat_model.py`, or new infrastructure routing adapters. |
| ENVIRONMENT_SETUP.md | `LLM_COMPLEXITY` and `LLM_ROUTER_DEBOUNCE_SECONDS` added to `settings.py`; no `.env` committed. Catalog client uses `httpx` (transitive at runtime; not declared as direct runtime dep). |

## Plan vs implementation

| Planned (changelog) | Actual (git/code) | Status |
| :--- | :--- | :--- |
| `domain/llm_routing.py` — ports and types | Implemented (untracked) | match (uncommitted) |
| `application/llm_router.py` — complexity + fallback | Implemented (untracked) | match (uncommitted) |
| `application/routing_chat_model.py` — LangChain adapter | Implemented (untracked) | match (uncommitted) |
| `application/llm.py` — route Groq through router | Modified in working tree | match (uncommitted) |
| `infrastructure/groq_model_catalog.py` | Implemented (untracked) | match (uncommitted) |
| `infrastructure/groq_model_registry.py` — 3 h deactivation | Implemented (untracked) | match (uncommitted) |
| `infrastructure/llm_debounce.py` | Implemented (untracked) | match (uncommitted) |
| `settings.py` — `LLM_COMPLEXITY`, `LLM_ROUTER_DEBOUNCE_SECONDS` | Modified in working tree | match (uncommitted) |
| `wiring.py` — `build_llm_router()` | Modified in working tree | match (uncommitted) |
| `tests/test_llm.py` — `test_llm13`–`test_llm20` | Added in working tree | match (uncommitted) |
| `changelog/.../tests/HOMOLOGATION.md` — routing note | Modified in working tree | match (uncommitted) |
| Deferred: OpenAI/Anthropic routing | Not implemented | match (deferred) |
| Deferred: Redis-backed registry | In-process only | match (deferred) |

## Layer review (application)

### Files reviewed

- `src/mcp_server/domain/llm_routing.py` — `LLMComplexity`, `GroqModelRecord`, catalog/registry/debounce ports; no framework imports
- `src/mcp_server/application/llm_router.py` — tier selection, fallback chain, token-limit deactivation, debounce before provider calls
- `src/mcp_server/application/routing_chat_model.py` — `BaseChatModel` delegating `_generate` / `_agenerate` to router
- `src/mcp_server/application/llm.py` — `create_chat_model` returns `RoutingChatModel`; router registration accessors
- `src/mcp_server/infrastructure/groq_model_catalog.py` — Groq `/v1/models` HTTP client
- `src/mcp_server/infrastructure/groq_model_registry.py` — free-model allowlist, timed deactivation expiry
- `src/mcp_server/infrastructure/llm_debounce.py` — `IntervalLLMDebounceGate`
- `src/mcp_server/wiring.py` — `build_llm_router()` wires catalog, registry, debounce, router; `build_chat_model` invokes router before factory
- `src/mcp_server/settings.py` — `llm_complexity`, `llm_router_debounce_seconds`
- `tests/test_llm.py` — routing helpers (`InMemoryGroqModelRegistry`, `_register_test_router`) and `test_llm13`–`test_llm20`

### Architecture & patterns

- Application `LLMRouter` depends on domain ports (`IGroqModelRegistry`, `ILLMDebounceGate`) and injected `GroqChatModelBuilder` — no infrastructure imports in application modules.
- `RoutingChatModel` is the sole Groq path from `create_chat_model`; `build_groq_chat_model` is confined to wiring's closure — matches investigation anti-pattern avoidance.
- Complexity tiers rank active models by `model_capability_score` and pick low/mid/high indices; `preferred_model_id` is honored at the front of the fallback chain (backward compatible with explicit `model_id`).
- Token-limit errors deactivate models for 3 hours via `registry.deactivate_until`; registry re-activates free models after expiry.
- `import-linter` contracts: 5 kept, 0 broken.

### Anti-patterns checked

- [x] No smart tools / leaky contexts / unvalidated I/O
- [x] Port/adapter boundaries respected
- [x] No secrets in source or changelog

## Findings

### Critical (must fix before merge)

- **IMPLEMENTATION3 deliverables are uncommitted.** At HEAD, no routing layer exists. Seven new source files (`llm_routing.py`, `llm_router.py`, `routing_chat_model.py`, `groq_model_catalog.py`, `groq_model_registry.py`, `llm_debounce.py`, plus changelog pair) are untracked; `llm.py`, `settings.py`, `wiring.py`, `tests/test_llm.py`, and `HOMOLOGATION.md` are modified but unstaged. Merging `develop` as-is would not ship the LLM routing layer.

### Warnings (should fix)

- **`create_chat_model(..., temperature=...)` ignores per-call temperature.** `llm.py` discards the resolved value (`_ = settings.llm_temperature if temperature is None else temperature`) instead of passing it to the router. Settings-level temperature still flows through `build_llm_router(settings)` at wiring time, but callers overriding temperature (e.g. `test_llm02` with `temperature=0.5`) no longer affect the built model — regression from IMPLEMENTATION1 behavior.
- **`ruff format --check src/` fails.** `groq_model_registry.py` and `wiring.py` would be reformatted; IMPLEMENTATION3 checklist item 12 is not fully satisfied.
- **Domain cooldown helper unused in router.** `token_limit_deactivation_until()` in `domain/llm_routing.py` is tested (`test_llm19`) but `LLMRouter` duplicates the 3-hour constant as `TOKEN_LIMIT_COOLDOWN_SECONDS` — drift risk if the domain policy changes.
- **`httpx` not a direct runtime dependency.** `GroqModelCatalogClient` imports `httpx`; it resolves transitively today (`uv run --no-dev` can import `httpx`), but INVESTIGATION3 recommended adding it explicitly to `[project.dependencies]` for production catalog fetches.
- **`build_llm_router()` invoked on every `build_chat_model()` call.** Rebuilds registry, re-registers globals, and re-fetches catalog; safe under lazy single init but resets deactivation state if `build_chat_model` is called more than once per process.
- **`build_llm_router` swallows only `RuntimeError` on initial catalog refresh.** Network/catalog failures raise `httpx` exceptions and fail startup; the narrow `except RuntimeError: pass` documents intent poorly and may hide future `RuntimeError` sources without logging.
- **Undocumented working-tree changes.** `pyproject.toml` (pytest `secrets_homologation` marker), `tests/test_secrets_homologation.py`, and `scripts/doppler/upload-local-env.sh` are outside IMPLEMENTATION3 scope — exclude from routing commit or document separately.
- **Debounce test coverage is async-only.** `test_llm17` exercises `acquire()` but not `acquire_sync()` used by `LLMRouter.generate()`.

### Suggestions (consider)

- Wire `LLMRouter` token-limit cooldown through `token_limit_deactivation_until()` to keep a single domain source of truth.
- Add `httpx` to runtime dependencies in `pyproject.toml`.
- Extend `test_llm02` to assert temperature propagation (via `router.set_temperature` or builder spy).
- Update `ARCHITECTURE.md` file map with routing modules.
- Log or metric when catalog refresh fails at wiring time instead of silent `pass`.

## Verification

| Command | Result |
| :--- | :--- |
| `uv run ruff check src/` | pass |
| `uv run ruff format --check src/` | **fail** — 2 files would be reformatted (`groq_model_registry.py`, `wiring.py`) |
| `uv run mypy src/` | pass |
| `uv run pytest tests/test_llm.py tests/test_llm_models.py` | pass (33 tests) |
| `npm run lint:architecture` | pass (5 contracts kept) |

## Verdict

**request changes**

Working-tree code matches INVESTIGATION3 / IMPLEMENTATION3, respects Clean Architecture boundaries, and passes mypy, ruff lint, architecture import contracts, and the LLM routing test slice. **Commit** all routing source files, tests, and changelog artifacts; run `ruff format` on the two flagged files; restore or document `create_chat_model` temperature override behavior before merge.
