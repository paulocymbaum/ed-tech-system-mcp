# Architecture Documentation: Domain-Driven MCP Server

Architectural standards for the ed-tech MCP server. Maintainability, testability, and scalability come from Domain-Driven Design (DDD), SOLID, and Clean Architecture.

## Core Design Principles

- **SOLID**: Single responsibility per module; composition over inheritance; Dependency Inversion at every boundary.
- **DRY**: Domain rules live once (validators, enums, ports). Tools and agents call them — they do not re-implement them.
- **Clean Code**: Names match domain concepts. Prefer small, testable units over framework glue in the core.

---

## Architectural Layers (Clean Architecture)

Concentric layers: **inner layers never import outer layers**. Dependency direction is always inward toward Domain.

```text
entrypoint / local UI
        ↓
   interface  (MCP tools, validation, error mapping)
        ↓
  application (workflows, LangGraph agents, runners)
        ↓
     domain   (entities, ports, invariants)  ←  infrastructure (adapters)
```

| Layer | Path under `src/mcp_server/` | May import | Must not import |
| :--- | :--- | :--- | :--- |
| **domain** | `domain/` | stdlib, pydantic (schemas only) | MCP SDK, LangChain/LangGraph, Supabase, HTTP clients, Redis |
| **application** | `application/` | domain, LangChain/LangGraph primitives | MCP SDK, concrete infrastructure adapters |
| **interface** | `interface/` | domain, application, MCP SDK, FastAPI (local UI) | infrastructure adapters directly (use ports via wiring/runtimes) |
| **infrastructure** | `infrastructure/` | domain ports, external SDKs | interface, MCP tool handlers |
| **entrypoint** | `main.py`, `wiring.py`, `settings.py`, … | all layers (composition root only) | — |

Cross-cutting **changelog folders** (`changelog/{DATE}/{LAYER}/`) use the same layer names plus audit/refactor folders — see [Changelog layer names](#changelog-layer-names).

---

### 1. Domain Layer (`domain/`)

Source of truth for business meaning. Pure Python + Pydantic models; no I/O.

**Responsibility**

- Entities and value objects (`schemas.py`, `content_schemas.py`, `harness_schemas.py`, `authoring.py`, …)
- Ports (ABCs) in `interfaces.py` and focused modules (`cache.py`, `project_review.py`, `socratic.py`, `token_counting.py`, …)
- Invariants, safety, and curriculum lockstep enums (`invariants.py`, `input_safety.py`, `curriculum_enums.py`, `content_validators.py`)
- Domain exceptions (`exceptions.py`)

**Key modules (illustrative)**

| Module | Role |
| :--- | :--- |
| `interfaces.py` | Ports: repositories, search, video, graph search, authoring backend factory |
| `curriculum_enums.py` | DB/FE lockstep enums (e.g. `project_file_kind`) |
| `content_validators.py` | Quiz/project/lesson validation used by authoring tools |
| `authoring.py` | Authoring DTOs and save contracts |
| `caller_identity.py` | Authenticated caller model for privileged tools |

---

### 2. Application Layer (`application/`)

Use-case orchestration. Depends on **domain ports**, not adapters.

**Responsibility**

- LangGraph agent packages under `agents/` (content generation, research article, Socratic, project review, Tavily/YouTube search graphs)
- Workflow runners and traces (`*_runner.py`, `workflow_*.py`)
- LLM factory and routing (`llm.py`, `llm_router.py`, `routing_chat_model.py`, `llm_models.py`)
- Authoring application services (`authoring_service.py`, `mock_test_authoring.py`)
- Runtime accessors set by wiring (`integration_runtime.py`, `mcp_tool_cache_runtime.py`, `mcp_tool_auth_runtime.py`, …)

**Agent packages** (`application/agents/<name>/`)

Each package typically owns `graph.py`, `nodes.py`, `state.py`, and optionally `prompts.py` / loaders. Graphs are invoked from interface tools or runners — not from infrastructure.

---

### 3. Interface Layer (`interface/`)

MCP adapters. Translates protocol I/O ↔ application/domain.

**Responsibility**

- MCP server and tool registration (`mcp_server.py`, `custom_tools*.py`)
- Pydantic request/response validation (`validation.py`, `validation_workflow.py`)
- Domain → protocol error mapping (`error_mapping.py`)
- Privileged tool auth gates (`privileged_tool_auth.py`)

**Tool modules**

| Module | Tools (names) |
| :--- | :--- |
| `custom_tools.py` | `health_check`, `search_youtube`, `build_lesson_enrichment_query` |
| `custom_tools_agent_workflows.py` | `research_article`, `content_generation` |
| `custom_tools_authoring.py` | `validate_*`, `save_to_backend`, `author_lesson_pipeline`, `search_graph_nodes`, `generate_mock_test_structure`, `validate_mock_test` |
| `custom_tools_socratic.py` | `socratic_tutor` |
| `custom_tools_project_review.py` | `collect_project_review_context`, `project_review` |

Tools must stay thin: validate → call application/domain → map errors. No Supabase or YouTube SDKs inside tool bodies.

---

### 4. Infrastructure Layer (`infrastructure/`)

Adapters that implement domain ports.

**Responsibility**

- Supabase / graph / project-review repositories
- Search and video clients (DuckDuckGo, Tavily, YouTube)
- Groq LLM adapter and model catalog/cache
- Redis / in-process cache, rate limiting, observability wrappers
- Authoring backend HTTP client (manager JWT + anon key → Supabase RPCs)

**Subpackages**

| Path | Role |
| :--- | :--- |
| `search_client/` | DuckDuckGo / Tavily web search adapters |
| `youtube_client/` | YouTube Data API v3 adapter |
| `token_counting/` | Tiktoken counter |

---

### 5. Entrypoint / Composition Root

Not a DDD “ring” but the only place allowed to construct the full graph.

| File | Role |
| :--- | :--- |
| `main.py` | MCP process entry (`mcp-server`) |
| `wiring.py` | `ApplicationContext`, DI, cache/auth/retrieval wiring |
| `settings.py` | Pydantic Settings (secrets + aliases, e.g. anon key) |
| `operational_config.py` | Non-secret `config.json` loader |
| `env_bootstrap.py` | Early env / logging bootstrap |
---

### 6. Tests (`tests/`)

Pytest suites mirror layers (`test_domain_*`, `test_interface_*`, infrastructure adapters, architecture lint). Fakes live under `tests/fakes/`. Architecture lint (`npm run lint:architecture` / `test_architecture_lint.py`) enforces import boundaries.

---

## Changelog layer names

Agent memory under `changelog/{YYYY-MM-DD}/{LAYER}/` uses:

| `{LAYER}` | Use for |
| :--- | :--- |
| `domain` | Entities, ports, validators, enums |
| `application` | Agents, runners, application services |
| `interface` | MCP tools, validation, UI API |
| `infrastructure` | Adapters, clients, cache, retrieval |
| `entrypoint` | Wiring, settings, process bootstrap |
| `tests` | Test inventories / homologation |
| `performance` | Performance audits |
| `code-health` | Maintainability audits |
| `refactor` | Merged refactor plans from audits |

Protocol and file roles: `.cursor/rules/changelog-agent-memory.mdc` and the [README documentation matrix](./README.md#documentation-matrix).

---

## File Structure (canonical tree)

```text
config.json
src/mcp_server/
├── domain/                 # Pure business logic + ports
├── application/            # Workflows, agents/, runners, LLM routing
│   └── agents/             # One package per LangGraph workflow
├── interface/              # MCP tools + validation
│   ├── custom_tools*.py
│   ├── validation.py
│   └── validation_workflow.py
├── infrastructure/         # Adapters (search, video, LLM, cache)
├── settings.py
├── operational_config.py
├── wiring.py               # Composition root
└── main.py
tests/                      # pytest + architecture lint
changelog/                  # Agent memory by date + layer (local)
```

---

## Dependency Stack & Usage

| Dependency | Primary use | Layer |
| :--- | :--- | :--- |
| `mcp` / FastMCP | Tool transport | Interface / entrypoint |
| `langchain` / `langgraph` | Agent graphs and orchestration | Application |
| `pydantic` v2 | Schemas and settings | Domain / Interface / Entrypoint |
| `supabase` | Postgres / RPC / vectors | Infrastructure |
| `duckduckgo-search` / Tavily | Web search | Infrastructure |
| `google-api-python-client` | YouTube Data API | Infrastructure |
| Redis client | Tool/LLM cache (when enabled) | Infrastructure |

---

## Core Patterns

### 1. Pydantic at the boundary
MCP tool inputs/outputs go through `interface/validation*.py` before application logic.

### 2. Ports & adapters
Define ports in Domain; implement in Infrastructure; inject via `wiring.py`. Application and tools never construct HTTP/DB clients.

### 3. Thin MCP tools
Decorator → validate → privileged auth (if needed) → application/service → map errors. No SQL, no YouTube SDK, no agent graph construction inside the tool module beyond invoking a runner.

### 4. Curriculum lockstep
Enums and shapes shared with Supabase / PraxisWeb (e.g. `project_file_kind`) live in `domain/curriculum_enums.py` and are covered by lockstep tests.

### 5. Schema evolution
Keep MCP external schemas, validation models, and domain entities distinct. Do not leak PostgREST or provider blobs to clients.

---

## Anti-Patterns (What to Avoid)

| Anti-Pattern | Why it hurts |
| :--- | :--- |
| **"Smart" tools** | Logic in the decorator bypasses tests and SRP |
| **Leaky MCP Context** | Couples domain/application to transport |
| **Unvalidated I/O** | Hallucinated tool args crash workflows |
| **Infrastructure imports in domain/application** | Breaks dependency rule; architecture lint fails |
| **Direct YouTube/Supabase in tools** | Untestable; skips ports |
| **Raw API leakage** | Provider fields waste tokens and break contracts |
| **Changelog layer mismatch** | Memory under the wrong `{LAYER}` is hard to resume |
