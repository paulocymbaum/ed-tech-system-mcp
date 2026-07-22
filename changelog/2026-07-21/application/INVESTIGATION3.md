# Investigation 3: LLM routing layer (complexity, fallback, debounce, dynamic Groq registry)

**Date:** 2026-07-21
**Layer:** application
**Status:** approved

## User request

Implement an LLM routing layer that replaces direct Groq calls with complexity-based model selection (levels 1–3), failure fallback, debounce, dynamic Groq model registry (free models active by default), and 3-hour deactivation on token-limit errors.

## Architecture alignment

- **Layers touched:** domain (routing ports/contracts), application (router orchestration, complexity mapping), infrastructure (Groq API fetch, registry, debounce, routing chat model adapter), entrypoint (wiring integration)
- **Patterns applied:** Ports & adapters for catalog/registry/debounce; application `LLMRouter` orchestrates selection and fallback; `RoutingChatModel` is the sole Groq execution surface; composition root wires concrete adapters
- **Anti-patterns avoided:** No direct `ChatGroq` in application; no `os.environ` in inner layers; no bypass of router at call sites; OpenAI/Anthropic remain static registry only

## Current state

| Asset | Status |
| :--- | :--- |
| `application/llm.py` | `create_chat_model()` calls registered Groq builder directly with static `llm_models` id |
| `application/llm_models.py` | Static Groq + OpenAI + Anthropic entries; no live catalog |
| `infrastructure/groq_adapter.py` | Thin `ChatGroq` factory — bypassed only via `create_chat_model` today |
| `wiring.py` | Registers Groq builder, calls `create_chat_model(settings)` — no router |
| `domain/interfaces.py` | No LLM routing ports |
| `tests/test_llm.py` | Factory/cache/graph tests; no routing, fallback, or registry behavior |

## Gap analysis

| Gap | Layer | Priority |
| :--- | :--- | :--- |
| No complexity → model mapping | application | P0 |
| No failure fallback chain | application | P0 |
| No debounce before Groq calls | infrastructure | P0 |
| No live Groq model catalog/registry | infrastructure | P0 |
| No token-limit deactivation (3 h) | infrastructure | P0 |
| Direct Groq builder in factory | application | P0 |
| No routing tests | tests | P0 |

## Minimal increment

Add domain ports (`IGroqModelCatalogClient`, `IGroqModelRegistry`, `ILLMDebounceGate`), infrastructure implementations (HTTP catalog fetch, in-memory registry with `active` flag and timed deactivation, asyncio debounce gate), application `LLMRouter` with complexity tiers and fallback execution, and `RoutingChatModel` wrapping all Groq `_generate`/`_agenerate` paths. Wire router at composition root so `build_chat_model` / `create_chat_model` never return raw `ChatGroq`. Add Settings fields for default complexity and debounce interval. Extend `test_llm.py` with routing contracts; update homologation doc.

### Scope (in)

- `domain/llm_routing.py` — types and ports
- `application/llm_router.py` — complexity mapping, fallback orchestration
- `application/routing_chat_model.py` — LangChain adapter delegating to router
- `application/llm.py` — route Groq path through router
- `infrastructure/groq_model_catalog.py` — Groq `/v1/models` fetch
- `infrastructure/groq_model_registry.py` — in-process registry + deactivation
- `infrastructure/llm_debounce.py` — configurable debounce gate
- `settings.py` — `LLM_COMPLEXITY`, `LLM_ROUTER_DEBOUNCE_SECONDS`
- `wiring.py` — build and inject router
- `tests/test_llm.py` — routing, fallback, deactivation, debounce tests
- `changelog/2026-07-21/tests/HOMOLOGATION.md` — note new routing coverage

### Scope (out / deferred)

- OpenAI/Anthropic routing (static registry unchanged)
- Paid model activation policy beyond default-inactive flag
- Redis-backed registry persistence across processes
- Operational `config.json` keys for debounce (env Settings sufficient for this increment)

## Proposed changes (files)

| File | Action | Rationale |
| :--- | :--- | :--- |
| `domain/llm_routing.py` | create | Ports and domain types |
| `application/llm_router.py` | create | Router orchestration |
| `application/routing_chat_model.py` | create | LangChain surface |
| `application/llm.py` | modify | Use router for Groq |
| `infrastructure/groq_model_catalog.py` | create | Live model list |
| `infrastructure/groq_model_registry.py` | create | Active flag + 3 h cooldown |
| `infrastructure/llm_debounce.py` | create | API overload guard |
| `settings.py` | modify | Router defaults |
| `wiring.py` | modify | Composition root |
| `tests/test_llm.py` | modify | Routing contracts |
| `changelog/2026-07-21/tests/HOMOLOGATION.md` | modify | Homologation note |

## Dependencies & environment

- Runtime deps: `httpx` (transitive via stack; add explicit if missing for catalog client)
- Dev deps: unchanged
- Secrets / env vars: `GROQ_API_KEY`, `LLM_COMPLEXITY`, `LLM_ROUTER_DEBOUNCE_SECONDS`
- Commands: `uv sync --frozen`, `uv run ruff check src/`, `uv run mypy src/`, `uv run pytest tests/test_llm.py tests/test_llm_models.py`

## Risks & open questions

- **Groq API free-tier metadata:** API list may not expose pricing; use known-free allowlist heuristic with `active=True`, others default `active=False`
- **Sync factory vs async catalog:** Initial registry refresh uses sync HTTP at wiring; async refresh on first invoke if empty
- **Explicit `model_id` in `create_chat_model`:** Honored as primary candidate in fallback chain (backward compatible with tests)

## Handoff to implementation

IMPLEMENTATION3.md: domain ports → infrastructure adapters → application router → llm/wiring → tests → ruff/mypy/pytest → homologation update.
