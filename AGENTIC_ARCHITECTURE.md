# Agentic Architecture: LangChain, LangGraph, and MCP Tool Orchestration

This document extends [ARCHITECTURE.md](./ARCHITECTURE.md). It defines how **language models**, **agents**, **tools**, and **data/search capabilities** are coupled inside the ed-tech MCP server.

`ARCHITECTURE.md` defines *where* code lives and *which dependencies are allowed per layer*. This document defines *how agentic execution flows* across those layers: LLM access, conditional parameter construction, tool invocation, and retrieval from Supabase, the web, and YouTube.

---

## Relationship to `ARCHITECTURE.md`

| Document | Scope |
| :--- | :--- |
| **ARCHITECTURE.md** | Clean Architecture layers, ports & adapters, validation boundaries, anti-patterns |
| **AGENTIC_ARCHITECTURE.md** | Agent graphs, LLM wiring, tool taxonomy, capability flows (DB / web / video), conditional parameters |

Both documents share the same layer names and restrictions. If they conflict, **ARCHITECTURE.md wins** on layer boundaries; this document wins on orchestration semantics.

---

## High-level execution model

External clients (Cursor, other MCP hosts) call **MCP tools**. MCP tools validate I/O, then delegate to **application workflows** or **LangGraph agents**. Agents may call **LangChain tools**, which invoke **domain ports** implemented in **infrastructure adapters**.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP client (LLM host)                                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ JSON-RPC tool call
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  INTERFACE — custom_tools.py                                            │
│  • MCP tool decorators (thin)                                           │
│  • Pydantic validation (validation.py)                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ validated DTOs
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  APPLICATION — workflows.py · agent.py · langchain_tools.py             │
│  • LangGraph state machine (nodes, edges, conditional routing)            │
│  • LangChain tools wrapping domain ports                                │
│  • Parameter builders (rules + optional LLM assistance)                   │
│  • Chat model access via injected LLM provider                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ port interfaces only
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DOMAIN — interfaces.py · schemas.py · query_policies.py                │
│  • IDataRepository · ISearchClient · IVideoSearchClient                 │
│  • ISqlReadExecutor (read-only SQL agent path)                           │
│  • Entities: DocumentHit, VideoResult, SqlQueryProposal                   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ adapter implementations
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE — supabase_client · search_client · youtube_client      │
│  • Supabase repository (structured queries)                             │
│  • Supabase SQL executor (sandboxed read-only SQL agent path)           │
│  • DuckDuckGo / Tavily web search                                       │
│  • YouTube Data API v3                                                  │
└─────────────────────────────────────────────────────────────────────────┘

         ▲
         │ composition root (wiring.py) injects adapters + LLM + caches
         │
┌────────┴────────────────────────────────────────────────────────────────┐
│  ENTRYPOINT — main.py · settings.py · wiring.py                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tool taxonomy

The word **tool** is used at three levels. Each level has a distinct contract and must not be conflated.

| Level | Name | Location | Consumed by | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **MCP tool** | `interface/custom_tools.py` | External MCP clients | Stable protocol surface; validate → delegate |
| **2** | **LangChain tool** | `application/langchain_tools.py` | LangGraph nodes / agents | LLM-callable capabilities with structured args |
| **3** | **Domain port** | `domain/interfaces.py` | Application layer only | Technology-agnostic integration contract |

### Coupling rules

1. **MCP tools never call Supabase, YouTube, or web APIs directly.** They delegate to application workflows or compiled LangGraph graphs.
2. **LangChain tools never import infrastructure.** They receive port implementations via dependency injection from `wiring.py`.
3. **LangGraph nodes** orchestrate: they may call LangChain tools, domain services, or parameter builders — never MCP SDK types.
4. **One capability may expose both an MCP tool and a LangChain tool** when external clients and internal agents need the same behavior. Shared logic lives in `application/workflows.py` or a domain service — not duplicated in decorators.

---

## Layer responsibilities (agentic view)

### 1. Domain (`src/mcp_server/domain/`)

Pure business rules and port definitions. No LangChain, MCP, or provider SDKs.

| Artifact | Role in agentic flows |
| :--- | :--- |
| `interfaces.py` | Ports: `IDataRepository`, `ISearchClient`, `IVideoSearchClient`, `ISqlReadExecutor` |
| `schemas.py` | Entities returned to upper layers: `DocumentHit`, `VideoResult` |
| `query_policies.py` *(planned)* | SQL allowlists, table/column policies, max row limits for the SQL agent path |
| `exceptions.py` | Domain failures surfaced to interface error mapping (`ResourceNotFoundError`, `DomainValidationError`) |
| `invariants.py` | Pure input guards shared by infrastructure adapters |

#### Supabase access — two domain modes

| Mode | Port | When to use |
| :--- | :--- | :--- |
| **Structured query** | `IDataRepository.find_documents(...)` | Known query shape: text search, filters, pagination, sort — parameters are explicit and validated |
| **SQL agent (read-only)** | `ISqlReadExecutor.execute(proposal)` | Open-ended analytical questions; LLM proposes SQL; domain policy validates before execution |

Structured mode is the **default**. SQL agent mode is **opt-in** per workflow and always passes through `SqlQueryProposal` validation and `query_policies` before any SQL reaches infrastructure.

---

### 2. Application (`src/mcp_server/application/`)

Orchestration, agents, LangChain tools, and conditional parameter construction.

| Module | Responsibility |
| :--- | :--- |
| `agent.py` | LangGraph graph definitions (`StateGraph`), node functions, `create_agent()` factory |
| `workflows.py` | Use-case orchestrators (e.g. `DocumentVideoWorkflow`) callable from MCP tools or graph terminal nodes |
| `langchain_tools.py` *(planned)* | `@tool` wrappers: `search_web`, `search_youtube`, `find_documents`, `run_sql_read` |
| `parameter_builders.py` *(planned)* | Build tool/agent parameters from graph state, user intent, and prior retrieval results |
| `llm.py` | `create_chat_model(settings)` — single factory for LLM access; no raw API keys in agents |
| `workflow_graph.py` | Graph introspection for local workflow UI |

#### Language model access

- LLMs are accessed **only** through `application/llm.py`, which returns a LangChain `BaseChatModel`.
- Credentials (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, model name, temperature) are loaded in **Settings** at the entrypoint and injected into `create_chat_model()`.
- Graph nodes that need reasoning import the chat model via **constructor injection** or a **runtime context** populated by `wiring.py` — never via `os.getenv()` inside nodes.
- LLM output that becomes tool arguments or SQL **must** be parsed into Pydantic models before any port call.

#### Conditional parameter building

Parameters are built in three stages:

```text
Graph state + user request
        │
        ▼
┌───────────────────┐
│ 1. Rule-based     │  Defaults, limits, safe_search, language, pagination caps
│    builder        │  (no LLM — deterministic)
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. Context merge  │  Enrich from prior nodes (e.g. document title → video query)
│    (graph state)  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. LLM assist     │  Optional: rephrase query, extract filters, draft SQL proposal
│    (parameter_    │  Output → Pydantic only; never raw dict to infrastructure
│     builders.py)  │
└─────────┬─────────┘
          │
          ▼
   Validated request DTO → LangChain tool or port
```

**Conditional routing** (which tools to call, which Supabase mode to use) is expressed as **LangGraph conditional edges** inspecting validated state — not as `if` branches inside MCP tool decorators.

Example routing rules:

| Condition | Route |
| :--- | :--- |
| User asks for videos only | `search_videos` node; skip `fetch_documents` |
| Documents found with rich metadata | `derive_search_terms` uses `documents[0].title` instead of raw query |
| User requests analytics / aggregation | SQL agent path (`propose_sql` → `validate_sql` → `execute_sql`) |
| User provides explicit filters (course_id, tags) | Structured `find_documents` with `DocumentQueryRequest` |

---

### 3. Interface (`src/mcp_server/interface/`)

MCP protocol adapter. The only layer that speaks JSON-RPC / FastMCP.

| Module | Responsibility |
| :--- | :--- |
| `mcp_server.py` | FastMCP instance and server factory |
| `custom_tools.py` | MCP tool registration — one function per external capability |
| `validation.py` | **All** MCP request/response Pydantic schemas |
| `local_ui/` | Local-only workflow visualization API (not part of MCP transport) |

#### MCP tool catalog

| MCP tool | Status | Validates with | Delegates to |
| :--- | :--- | :--- | :--- |
| `health_check` | ✅ | — | inline |
| `find_documents` | ✅ | `DocumentQueryRequest` → `DocumentQueryResponse` | `DocumentVideoWorkflow.retrieve_with_videos` (parallel I/O) |
| `search_youtube` | ✅ | `VideoSearchRequest` → `VideoSearchResponse` | `DocumentVideoWorkflow.search_videos` |
| `run_workflow` | ✅ | `WorkflowRunRequest` → `WorkflowRunResponse` | `run_document_video_graph` (sequential LangGraph) |
| `search_web` | 📋 planned | `WebSearchRequest` → `WebSearchResponse` | web search LangChain tool / workflow |
| `query_supabase_sql` | 📋 planned | `SqlAgentRequest` → `SqlAgentResponse` | SQL agent subgraph (read-only) |

Every MCP tool follows the same template:

```text
receive raw args → Pydantic validate → call application → Pydantic validate response → return
```

---

### 4. Infrastructure (`src/mcp_server/infrastructure/`)

Concrete adapters. The only layer that imports Supabase, DuckDuckGo, YouTube, and Redis clients.

| Adapter | Port | Agentic capability |
| :--- | :--- | :--- |
| `supabase_client.py` | `IDataRepository` | Structured document retrieval (parameterized queries / RPC / filtered select) |
| `supabase_sql_executor.py` *(planned)* | `ISqlReadExecutor` | Execute **validated** read-only SQL against allowlisted views |
| `search_client.py` | `ISearchClient` | Web search snippets for agent context |
| `youtube_client.py` | `IVideoSearchClient` | Normalized `VideoResult` list |
| `cached_adapters.py` | wraps above | Cache-aside for repeated agent tool calls |
| `cached_llm.py` | wraps `BaseChatModel` | Cache-aside for LLM completions (**async path only** — see below) |
| `mcp_tool_cache.py` | — | Optional MCP tool I/O caching at the interface boundary |

#### Supabase — structured queries (`IDataRepository`)

Infrastructure implements `find_documents` using **explicit, parameterized** Supabase operations:

- Full-text or `ilike` search on `query`
- Optional filters: `course_id`, `topic_tags`, `language`, `published_after`
- `limit` / `offset` enforced at validation and again in the adapter (defense in depth)

The LLM never constructs raw PostgREST URLs. It may only populate fields on `DocumentQueryRequest`, which maps to a fixed query template in the adapter.

#### Supabase — SQL agent path (`ISqlReadExecutor`)

For open-ended read questions:

1. Application node calls LLM with schema context (allowlisted tables/columns from `query_policies.py`).
2. LLM output is parsed into `SqlQueryProposal` (SQL string + bound parameters).
3. Domain policy validates: `SELECT` only, no `;`, no DDL/DML, table allowlist, row limit.
4. Infrastructure executes via **parameterized** `supabase.rpc('execute_read_query', ...)` or a read-only DB role.
5. Results are normalized to `list[dict[str, Any]]` or domain entities before returning to the agent.

SQL agent and structured query **share the same Supabase connection** but **never share the same code path** without validation.

#### Web search (`ISearchClient`)

- Input: `query`, `max_results` (validated, capped).
- Output: `list[str]` snippets — not raw provider JSON.
- Used by agents for real-time context enrichment and by optional sparse-document enrichment (planned).

**Wiring status (BL-005, 2026-07-21):** `build_search_client()` exists in `wiring.py` but is **not** injected at the composition root yet. The DuckDuckGo adapter remains a stub (BL-022). Defer wiring until:

1. `application/langchain_tools.py` ships `search_web` (LangChain tool wrapping `ISearchClient`), and
2. MCP `search_web` tool delegates through that LangChain tool or a dedicated workflow step.

**Target injection path (not `DocumentVideoWorkflow` in the current increment):**

```text
wiring.build_search_client(settings, cache)
  → application/langchain_tools.search_web (planned)
  → MCP search_web tool (planned)
  → optional application/agents/web_enrich subgraph when documents are sparse
```

`DocumentVideoWorkflow` continues to use only `IDataRepository` + `IVideoSearchClient`. Web search enrichment is a separate capability path to avoid coupling document+video discovery to an unwired stub adapter.

#### LLM completion cache (`CachedChatModel`)

`CachedChatModel` wraps the chat model built by `application/llm.py` at the composition root (`wiring.py`). It applies cache-aside on **`_agenerate` only** (the path used by `ainvoke` and LangGraph async nodes). The sync `_generate` method delegates to the inner model without cache lookup or store.

| Path | Cached? | When used |
| :--- | :--- | :--- |
| `_agenerate` / `ainvoke` | Yes (when `CACHE_ENABLED` and rule enabled) | LangGraph agents, async workflows |
| `_generate` / `invoke` | No — always calls provider | No current production callers; sync cache deferred |

TTL and key prefix: `CACHE_TTL_LLM_COMPLETION`, `CACHE_KEY_PREFIX_LLM` (see env table below).

#### YouTube search (`IVideoSearchClient`)

- Input: `query`, `max_results`, `language`, `safe_search` (see `VideoSearchRequest` in `validation.py`).
- Output: `list[VideoResult]` — normalized domain entities.
- Often chained after document retrieval: search terms derived from document metadata, not the raw user prompt.

---

### 5. Entrypoint (`main.py`, `settings.py`, `wiring.py`)

Composition root and transport bootstrap.

| Concern | Where |
| :--- | :--- |
| Load secrets / Settings | `settings.py`, `main.py` (`bootstrap_environment`) |
| Wire ports → workflows → agents | `wiring.py` |
| Start MCP transport | `main.py` → `create_mcp_server().run()` |
| Local workflow UI | `local_ui_main.py` (development only) |

#### `wiring.py` responsibilities *(target)*

```text
build_data_repository(settings, cache)     → IDataRepository
build_search_client(settings, cache)       → ISearchClient
build_video_client(settings, cache)        → IVideoSearchClient
build_sql_executor(settings)               → ISqlReadExecutor
build_langchain_tools(ports...)            → list[BaseTool]
build_document_video_workflow(ports...)    → DocumentVideoWorkflow
build_agent(settings, ports, tools, llm)   → CompiledStateGraph
register_mcp_tools(workflow, agent, ...)   → side effect on custom_tools.py / mcp
```

`main()` must call `register_mcp_tools(...)` after wiring so MCP decorators receive injected dependencies — not global singletons with lazy `os.getenv()`.

---

## Capability flows

### A. Find documents (structured Supabase)

```text
MCP: find_documents(query, course_id?, tags?, limit?)
  → DocumentQueryRequest validation
  → DocumentVideoWorkflow.retrieve_with_videos() OR document-only subgraph
  → IDataRepository.find_documents(query, limit, filters...)
  → SupabaseRepository (parameterized select / RPC)
  → list[DocumentHit]
  → DocumentQueryResponse validation
  → MCP client
```

### B. Query Supabase (SQL agent, read-only)

```text
MCP: query_supabase_sql(natural_language_question, context?)
  → SqlAgentRequest validation
  → LangGraph: propose_sql node (LLM + schema context)
  → SqlQueryProposal validation
  → domain query_policies.validate(proposal)
  → ISqlReadExecutor.execute(proposal)
  → SqlAgentResponse validation (rows + explanation)
  → MCP client
```

### C. Search the web

```text
MCP: search_web(query, max_results?)
  → WebSearchRequest validation
  → LangChain tool search_web OR direct workflow step
  → ISearchClient.search(query, max_results)
  → DuckDuckGoSearchClient
  → WebSearchResponse validation
  → MCP client
```

### D. Search YouTube videos

```text
MCP: search_youtube(query, max_results?, language?, safe_search?)
  → VideoSearchRequest validation (existing schema)
  → LangChain tool search_youtube OR DocumentVideoWorkflow
  → IVideoSearchClient.search_videos(...)
  → YouTubeDataApiClient
  → VideoSearchResponse validation
  → MCP client
```

### E. Full agent workflow (document + video)

```text
MCP: run_workflow(query, document_limit?, video_limit?)
  → WorkflowRunRequest validation
  → run_document_video_graph() — sequential LangGraph path (per-node observability)
      fetch_documents     → IDataRepository
      derive_search_terms → rule-based from documents[0].title or query
      search_videos       → IVideoSearchClient
      merge_results       → combine DocumentHit + VideoResult in state
  → WorkflowRunResponse validation (pruned DocumentSummary payloads)
  → MCP client
```

**Latency note:** MCP `find_documents` uses `DocumentVideoWorkflow.retrieve_with_videos` with BL-010 optimistic parallel I/O. MCP `run_workflow` uses the sequential LangGraph path above for step visibility and workflow timeout enforcement — not the parallel composite method.

---

## Validation schema map

| Schema | Layer file | Used by |
| :--- | :--- | :--- |
| `DocumentSummary` | `interface/validation.py` | Pruned document DTO in MCP responses (BL-013) |
| `DocumentQueryRequest` / `DocumentQueryResponse` | `interface/validation.py` | MCP `find_documents` |
| `VideoSearchRequest` / `VideoSearchResponse` | `interface/validation.py` | MCP `search_youtube` |
| `WorkflowRunRequest` / `WorkflowRunResponse` | `interface/validation.py` | MCP `run_workflow`, local UI POST run |
| `WebSearchRequest` / `WebSearchResponse` *(planned)* | `interface/validation.py` | MCP `search_web` |
| `SqlAgentRequest` / `SqlAgentResponse` *(planned)* | `interface/validation.py` | MCP `query_supabase_sql` |
| `SqlQueryProposal` *(planned)* | `domain/schemas.py` or `validation.py` | LLM → SQL agent gate |
| `DocumentHit`, `VideoResult` | `domain/schemas.py` | Internal entity boundary |

---

## LangGraph agent design

### State

Each graph defines a `TypedDict` state (e.g. `DocumentVideoState` in `agent.py`). State fields are:

- **Inputs** — user query, limits, flags
- **Intermediate** — retrieved documents, derived search terms, tool outputs
- **Outputs** — merged results, counts, error markers

State is the **only** shared memory between nodes. Nodes return partial state updates as `dict` fragments.

### Nodes

| Node type | Calls | Example |
| :--- | :--- | :--- |
| **Retrieval** | Domain port via injected dependency | `fetch_documents` |
| **Transform** | Parameter builder (rules / LLM) | `derive_search_terms` |
| **Tool** | LangChain tool | `search_videos` |
| **Merge** | Pure Python on state | `merge_results` |
| **Route** | Conditional edge function | `route_by_intent` |

### Graph registration

`list_registered_workflows()` in `agent.py` registers compiled graphs for the local workflow UI. Production MCP exposure uses `create_agent()` and dedicated MCP tools — both compile the same graph definitions, not duplicate logic.

---

## Agent file structure

The tree below is the **canonical layout** for runtime agents, LangGraph workflows, LangChain tools, and related wiring. It extends the base layout in [ARCHITECTURE.md](./ARCHITECTURE.md) with agent-specific modules.

**Legend:** ✅ exists today · 📋 planned (named in this doc, not yet on disk)

```text
ed-tech-system-mcp/
│
├── AGENTIC_ARCHITECTURE.md              # This document
├── ARCHITECTURE.md                      # Layer boundaries and core patterns
├── config.json                          # ✅ Operational tuning (retries, workflow timeouts)
│
├── scripts/dev/
│   └── run-workflow-ui.sh               # ✅ Local dev: FastAPI + React workflow explorer
│
├── ui/                                  # ✅ Local workflow UI (dev only — not MCP transport)
│   ├── package.json
│   ├── vite.config.ts                   # Proxies /api → 127.0.0.1:8877
│   └── src/
│       ├── App.tsx                      # Workflow list + graph canvas
│       ├── api/workflows.ts             # Fetches /api/workflows from local_ui
│       └── components/
│           └── WorkflowGraphView.tsx    # React Flow graph renderer
│
├── tests/
│   ├── application/
│   │   ├── test_agent.py                # 📋 Graph compile, node routing, state updates
│   │   ├── test_parameter_builders.py   # 📋 Conditional param construction
│   │   └── test_langchain_tools.py      # 📋 LangChain tool → port delegation
│   ├── interface/
│   │   ├── test_custom_tools.py         # 📋 MCP tool validate → delegate
│   │   └── test_local_ui_api.py         # ✅ Local workflow UI API
│   ├── infrastructure/
│   │   ├── test_supabase_repository.py  # 📋 Structured document queries
│   │   └── test_sql_executor.py         # 📋 Read-only SQL agent path
│   └── test_cache.py                    # ✅ Cache-aside + wiring smoke tests
│
└── src/
    └── mcp_server/
        │
        ├── main.py                      # ✅ MCP entrypoint — bootstrap, settings, server.run()
        ├── local_ui_main.py             # ✅ Local workflow UI entrypoint (loopback only)
        ├── settings.py                  # ✅ Typed config; 📋 LLM + SQL agent fields
        ├── operational_config.py        # ✅ Pydantic loader for repo-root config.json
        ├── wiring.py                    # ✅ Composition root — ports, workflows, cache
        │                                # 📋 + langchain tools, agents, MCP registration
        │
        ├── domain/                      # Pure contracts — no LangChain / MCP / SDKs
        │   ├── interfaces.py            # ✅ IDataRepository, ISearchClient, IVideoSearchClient
        │   │                            # 📋 ISqlReadExecutor
        │   ├── schemas.py               # ✅ DocumentHit, VideoResult
        │   │                            # 📋 SqlQueryProposal, SqlQueryResult
        │   ├── query_policies.py        # 📋 SQL allowlists, table/column caps, SELECT-only rules
        │   ├── cache.py                 # ✅ ICacheStore port
        │   ├── cache_keys.py            # ✅ Deterministic cache key builders
        │   └── exceptions.py            # ✅ Domain errors → interface mapping
        │
        ├── application/                 # Agents, graphs, LangChain tools, orchestration
        │   ├── agent.py                 # ✅ create_agent(), list_registered_workflows()
        │   │                            # 📋 thin facade → agents/* graphs
        │   ├── workflow_graph.py        # ✅ Graph introspection DTOs (local UI)
        │   ├── workflow_config.py       # ✅ WorkflowExecutionConfig runtime view (wiring init)
        │   ├── llm_models.py            # ✅ AVAILABLE_LANGUAGE_MODELS registry
        │   ├── workflows.py             # ✅ DocumentVideoWorkflow use-case orchestrator
        │   ├── llm.py                   # ✅ create_chat_model(settings) → BaseChatModel
        │   ├── parameter_builders.py    # 📋 Rule + state + optional LLM param builders
        │   ├── langchain_tools.py       # 📋 @tool wrappers (web, youtube, documents, sql)
        │   │
        │   └── agents/                  # 📋 One package per LangGraph workflow
        │       ├── __init__.py          #     Re-exports compiled graphs for wiring/UI
        │       ├── document_video/      #     Document + YouTube discovery graph
        │       │   ├── state.py         #     DocumentVideoState TypedDict
        │       │   ├── nodes.py         #     fetch_documents, derive_search_terms, …
        │       │   └── graph.py         #     StateGraph wiring + compile()
        │       ├── sql_read/            #     Read-only Supabase SQL agent graph
        │       │   ├── state.py         #     SqlReadState TypedDict
        │       │   ├── nodes.py         #     propose_sql, validate_sql, execute_sql
        │       │   └── graph.py
        │       └── web_enrich/          #     Optional: web search enrichment subgraph
        │           ├── state.py
        │           ├── nodes.py
        │           └── graph.py
        │
        ├── interface/                   # MCP protocol + local UI adapters
        │   ├── mcp_server.py            # ✅ FastMCP instance
        │   ├── custom_tools.py          # ✅ health_check, find_documents, search_youtube, run_workflow
        │   │                            # 📋 search_web, query_supabase_sql
        │   ├── validation.py            # ✅ DocumentSummary, DocumentQuery*, VideoSearch*,
        │   │                            #     WorkflowRun*; 📋 WebSearch*, SqlAgent*
        │   └── local_ui/                # ✅ FastAPI adapter (dev-only workflow explorer)
        │       ├── api.py               #     GET /api/workflows, POST /api/workflows/{id}/run
        │       └── schemas.py
        │
        └── infrastructure/              # Provider adapters — only layer with external SDKs
            ├── supabase_client.py       # ✅ IDataRepository (stub)
            ├── supabase_sql_executor.py # 📋 ISqlReadExecutor — parameterized read-only SQL
            ├── search_client.py         # ✅ ISearchClient (stub)
            ├── youtube_client.py        # ✅ IVideoSearchClient (stub)
            ├── cached_adapters.py       # ✅ Cache-aside wrappers for ports
            ├── cache_config.py          # ✅ Per-operation TTL rules
            ├── redis_cache_store.py     # ✅ Redis ICacheStore
            ├── mcp_tool_cache.py        # ✅ MCP tool I/O cache helper
            ├── groq_adapter.py          # ✅ Groq ChatGroq adapter
            └── cached_llm.py            # ✅ Cache-aside wrapper (async _agenerate only)
```

### Module roles (agent-related)

| Path | Layer | Agentic responsibility |
| :--- | :--- | :--- |
| `application/agents/*/graph.py` | Application | Define and compile a LangGraph `StateGraph` |
| `application/agents/*/nodes.py` | Application | Node functions; call LangChain tools or ports via injection |
| `application/agents/*/state.py` | Application | `TypedDict` shared state for one workflow |
| `application/langchain_tools.py` | Application | LLM-callable tools wrapping domain ports |
| `application/parameter_builders.py` | Application | Build validated tool/agent params from state + rules + optional LLM |
| `application/llm.py` | Application | Single chat-model factory; credentials from Settings |
| `application/workflows.py` | Application | Imperative orchestrators shared by MCP tools and graph terminal nodes |
| `application/agent.py` | Application | Public factory (`create_agent`) and workflow registry for UI |
| `interface/custom_tools.py` | Interface | MCP tool surface — validate in, delegate out |
| `interface/validation.py` | Interface | All MCP request/response Pydantic models |
| `domain/query_policies.py` | Domain | SQL agent safety rules before execution |
| `infrastructure/supabase_sql_executor.py` | Infrastructure | Execute validated `SqlQueryProposal` only |
| `wiring.py` | Entrypoint | Wire ports → LangChain tools → graphs → MCP tool handlers |
| `ui/` + `interface/local_ui/` | Dev tooling | Visualize registered graphs locally (not production MCP) |

### Growth path: flat → packaged agents

Today `application/agent.py` holds the first graph inline. As more workflows are added:

1. Move each graph into `application/agents/<name>/` (`state.py`, `nodes.py`, `graph.py`).
2. Keep `agent.py` as a **facade** that re-exports `create_agent()` and `list_registered_workflows()` so `wiring.py` and the local UI have a stable import path.
3. Add matching tests under `tests/application/agents/<name>/`.
4. Register new graphs in `list_registered_workflows()` for the local UI and expose via MCP through `custom_tools.py`.

### Cursor build agents (repository tooling — not runtime)

These live under `.cursor/` and orchestrate **how the codebase is built**, not how the MCP server runs at runtime. They reference `ARCHITECTURE.md` and `AGENTIC_ARCHITECTURE.md` when implementing features.

```text
.cursor/
├── agents/
│   ├── master.md                        # Orchestrates build → review → remediate → homologate
│   ├── incremental-layer-builder.md     # Investigation + implementation per layer
│   ├── changelog-code-reviewer.md       # Code review vs changelog plans
│   └── test-homologator.md              # Test inventory + HOMOLOGATION.md
├── rules/
│   ├── changelog-agent-memory.mdc       # changelog/ folder protocol
│   └── secrets-env-safety.mdc           # Doppler + hook safety rules
└── skills/
    └── doppler-env-setup/SKILL.md       # Secrets bootstrap skill for build agents
```

| Artifact | Couples with |
| :--- | :--- |
| `.cursor/agents/master.md` | Subagents in fixed sequence; `changelog/` memory |
| `.cursor/agents/incremental-layer-builder.md` | `ARCHITECTURE.md`, layer paths under `src/mcp_server/` |
| `.cursor/skills/*/SKILL.md` | Invoked by agents for specialized setup (e.g. Doppler) |
| `scripts/hooks/*.sh` | Git pre-commit guards (secrets, `.env` blocks) — not runtime hooks |

Do not confuse **Cursor build agents** (`.cursor/agents/`) with **runtime LangGraph agents** (`application/agents/`). Only the latter execute inside the MCP server process.

---

## Settings and secrets (agentic extensions)

Extend `Settings` in `settings.py` *(planned fields)*:

| Variable | Used by |
| :--- | :--- |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | `application/llm.py` *(deferred)* |
| `GROQ_API_KEY` | `application/llm.py` via `create_chat_model()` |
| `LLM_MODEL`, `LLM_TEMPERATURE` | Chat model factory defaults |
| `CACHE_TTL_LLM_COMPLETION`, `CACHE_KEY_PREFIX_LLM` | `CachedChatModel` cache-aside |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Repository + SQL executor |
| `YOUTUBE_API_KEY` | Video search adapter |
| `SQL_AGENT_ENABLED` | Gate SQL agent MCP tool and graph routes |
| `SQL_AGENT_MAX_ROWS` | Domain query policy default |

All keys are `SecretStr`, loaded at entrypoint, injected via `wiring.py`. Never embedded in LangChain prompts or tool descriptions.

---

## Anti-patterns (agentic)

| Anti-pattern | Why it fails |
| :--- | :--- |
| LLM emits SQL → executed without `SqlQueryProposal` + policy check | SQL injection; schema escape |
| Structured and SQL paths mixed in one adapter method | Untestable; unclear contract |
| MCP tool calls LangChain agent internally, agent calls same MCP tool | Infinite recursion; protocol leak |
| Parameter builder returns unvalidated dict to infrastructure | Hallucinated filters crash adapters |
| LangChain tool imports `supabase` or `googleapiclient` | Breaks Clean Architecture |
| Global chat model singleton with lazy env read | Untestable; breaks CI without keys |
| Returning raw Supabase / YouTube / DDG payloads to MCP client | Token waste; schema boundary violation |

---

## File map (quick reference)

See [Agent file structure](#agent-file-structure) for the full tree. Status snapshot:

| Path | Status | Agentic role |
| :--- | :--- | :--- |
| `application/agent.py` | ✅ | LangGraph facade, `run_document_video_graph`, workflow registry |
| `application/agents/` | 📋 | One package per LangGraph workflow |
| `application/workflows.py` | ✅ | Use-case orchestration; BL-010 parallel `retrieve_with_videos` |
| `application/workflow_graph.py` | ✅ | UI introspection |
| `application/workflow_config.py` | ✅ | Runtime workflow limits (initialized at startup) |
| `application/llm_models.py` | ✅ | Typed LLM model registry for future factory |
| `application/langchain_tools.py` | 📋 | LangChain `@tool` wrappers |
| `application/parameter_builders.py` | 📋 | Conditional parameter construction |
| `application/llm.py` | ✅ | LLM factory (Groq-first; OpenAI/Anthropic deferred) |
| `interface/custom_tools.py` | ✅ | MCP tools: `health_check`, `find_documents`, `search_youtube`, `run_workflow` |
| `interface/validation.py` | ✅ | `DocumentSummary`, `DocumentQuery*`, `VideoSearch*`, `WorkflowRun*` |
| `interface/local_ui/` | ✅ | Local workflow explorer API + POST run endpoint |
| `domain/query_policies.py` | 📋 | SQL agent safety |
| `infrastructure/supabase_sql_executor.py` | 📋 | Read-only SQL execution |
| `operational_config.py` | ✅ | Load and validate repo-root `config.json` |
| `wiring.py` | partial | Composition; `build_search_client` deferred until BL-022 + `langchain_tools` |
| `ui/` | ✅ | React workflow graph viewer (local dev) |

---

## Implementation order

When building agentic features, follow the layer order from [changelog agent memory](./.cursor/rules/changelog-agent-memory.mdc):

```text
domain (ports + policies + entities)
  → application (LangChain tools, parameter builders, graph nodes)
  → infrastructure (adapter implementations)
  → interface (MCP tools + validation schemas)
  → entrypoint (wiring + settings)
  → tests
```

Within application layer, prefer this sequence:

1. Structured Supabase path (`DocumentQueryRequest` + repository implementation)
2. Web and YouTube LangChain tools (ports already defined)
3. Parameter builders and conditional graph edges
4. LLM factory and optional LLM-assisted parameter nodes
5. SQL agent path (policies + executor + MCP tool) — last, highest risk

---

## Summary

| Concern | Owner layer | Mechanism |
| :--- | :--- | :--- |
| LLM access | Application (`llm.py`) | Injected `BaseChatModel`; no keys in nodes |
| Conditional parameters | Application (`parameter_builders.py` + graph edges) | Rules → state merge → optional LLM → Pydantic |
| Tool calling (external) | Interface (`custom_tools.py`) | MCP tools validate and delegate |
| Tool calling (internal) | Application (`langchain_tools.py`) | LangChain tools wrap domain ports |
| Supabase structured read | Infrastructure → `IDataRepository` | Validated query params; fixed templates |
| Supabase SQL agent | Application + Domain + Infrastructure | LLM proposes → policy validates → `ISqlReadExecutor` |
| Web search | Infrastructure → `ISearchClient` | Normalized snippets |
| YouTube search | Infrastructure → `IVideoSearchClient` | Normalized `VideoResult` |
| Wiring | Entrypoint (`wiring.py`) | Single composition root for all dependencies |

This architecture keeps **reasoning** (LLM + LangGraph) in the application layer, **contracts** in the domain, **protocol exposure** in the interface, and **provider details** in infrastructure — consistent with [ARCHITECTURE.md](./ARCHITECTURE.md).
