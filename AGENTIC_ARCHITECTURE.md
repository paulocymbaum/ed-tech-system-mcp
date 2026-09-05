# Agentic Architecture: LangChain, LangGraph, and MCP Tool Orchestration

This document extends [ARCHITECTURE.md](./ARCHITECTURE.md). It defines how **language models**, **agents**, **tools**, and **data/search capabilities** are coupled inside the ed-tech MCP server.

`ARCHITECTURE.md` defines *where* code lives and *which dependencies are allowed per layer*. This document defines *how agentic execution flows* across those layers: LLM access, conditional parameter construction, tool invocation, and search/video integrations.

> **RAG removal note:** The MCP server no longer runs document embedding, vector retrieval, chunking, reranking, or the `find_documents` / `run_workflow` tools. Document RAG lives in the backend (`ed-tech-system-backend` embedding service + `mcp-find-documents` edge function). This codebase now focuses on LLM orchestration, web/YouTube search, and authoring workflows.

---

## Relationship to `ARCHITECTURE.md`

| Document | Scope |
| :--- | :--- |
| **ARCHITECTURE.md** | Clean Architecture layers, ports & adapters, validation boundaries, anti-patterns |
| **AGENTIC_ARCHITECTURE.md** | Agent graphs, LLM wiring, tool taxonomy, capability flows (web / video / authoring) |
| **[OBSERVABILITY.md](./OBSERVABILITY.md)** | Execution trace, LLM I/O inspection, debugging |

Both documents share the same layer names and restrictions. If they conflict, **ARCHITECTURE.md wins** on layer boundaries; this document wins on orchestration semantics.

---

## High-level execution model

External MCP clients call **MCP tools**. MCP tools validate I/O, then delegate to **application workflows** or **LangGraph agents**. Agents may call **LangChain tools**, which invoke **domain ports** implemented in **infrastructure adapters**.

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
│  APPLICATION — agent.py · langchain_tools.py · agents/*                 │
│  • LangGraph state machine (nodes, edges, conditional routing)            │
│  • LangChain tools wrapping domain ports                                │
│  • Parameter builders (rules + optional LLM assistance)                 │
│  • Chat model access via injected LLM provider                            │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ port interfaces only
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DOMAIN — interfaces.py · schemas.py · content_schemas.py                 │
│  • ISearchClient · IVideoSearchClient · authoring ports                    │
│  • Entities: VideoResult, lesson/quiz/PBL drafts                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ adapter implementations
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE — tavily_search_client · search_client · youtube_client   │
│  • Groq adapter, cache, rate limiting, authoring backend client             │
└─────────────────────────────┘
         ▲
         │ composition root (wiring.py) injects adapters + LLM + caches
         │
┌────────┴────────────────────────────────────────────────────────────────┐
│  ENTRYPOINT — main.py · settings.py · wiring.py                           │
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
4. **One capability may expose both an MCP tool and a LangChain tool** when external clients and internal agents need the same behavior. Shared logic lives in an application service or domain service — not duplicated in decorators.

---

## Layer responsibilities (agentic view)

### 1. Domain (`src/mcp_server/domain/`)

Pure business rules and port definitions. No LangChain, MCP, or provider SDKs.

| Artifact | Role in agentic flows |
| :--- | :--- |
| `interfaces.py` | Ports: `ISearchClient`, `IVideoSearchClient`, authoring backend factory, graph search |
| `schemas.py` | Entities returned to upper layers: `VideoResult`, graph entities/relations |
| `content_schemas.py` | Lesson/quiz/PBL draft contracts shared by content generation and authoring tools |
| `exceptions.py` | Domain failures surfaced to interface error mapping (`ResourceNotFoundError`, `DomainValidationError`) |
| `invariants.py` | Pure input guards shared by infrastructure adapters |

---

### 2. Application Layer (`application/`)

Use-case orchestration. Depends on **domain ports**, not adapters.

| Module | Responsibility |
| :--- | :--- |
| `agent.py` | LangGraph graph definitions, workflow registration |
| `integration_runtime.py` | Lazy accessors for `ISearchClient` and `IVideoSearchClient` (Tavily / YouTube) |
| `workflow_trace.py` | `invoke_graph_with_trace()` — per-node replay |
| `workflow_llm_trace.py` | Captures LLM prompts, raw output, and model name per node |
| `llm.py` / `llm_router.py` | `create_chat_model()`, Groq `LLMRouter` with per-complexity debounce and capped model fallback |
| `workflow_graph.py` | Graph introspection DTOs, spine layout, async/retry edge classification |
| `agents/*/` | One package per LangGraph workflow (`content_generation`, `course_scaffold`, `research_article`, `tavily_search`, `youtube_search`, `project_review`, `socratic`) |
| `langchain_tools.py` *(planned)* | `@tool` wrappers: `search_web`, `search_youtube` |
| `parameter_builders.py` *(planned)* | Build tool/agent parameters from graph state, user intent, and prior retrieval results |

#### Language model access

- LLMs are accessed **only** through `application/llm.py`, which returns a LangChain `BaseChatModel`.
- Credentials (`GROQ_API_KEY`, model name, temperature) are loaded in **Settings** at the entrypoint and injected into `create_chat_model()`.
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
│ 3. LLM assist     │  Optional: rephrase query, extract filters
│    (parameter_    │  Output → Pydantic only; never raw dict to infrastructure
│     builders.py)  │
└─────────┬─────────┘
          │
          ▼
   Validated request DTO → LangChain tool or port
```

**Conditional routing** (which tools to call) is expressed as **LangGraph conditional edges** inspecting validated state — not as `if` branches inside MCP tool decorators.

---

### 3. Interface Layer (`interface/`)

MCP protocol adapter. The only layer that speaks JSON-RPC / FastMCP.

| Module | Responsibility |
| :--- | :--- |
| `mcp_server.py` | FastMCP instance and server factory |
| `custom_tools.py` | MCP tool registration — one function per external capability |
| `validation.py` | **All** MCP request/response Pydantic schemas |
| `validation_workflow.py` | Workflow run schemas used by scripted tests and any future API |
| `error_mapping.py` | Domain → protocol error mapping |
| `privileged_tool_auth.py` | Authenticated caller gates for privileged tools |

#### MCP tool catalog

| MCP tool | Status | Validates with | Delegates to |
| :--- | :--- | :--- | :--- |
| `health_check` | ✅ | — | inline |
| `build_lesson_enrichment_query` | ✅ | `BuildLessonEnrichmentQueryRequest` | Lightweight LLM term expansion |
| `search_youtube` | ✅ | `VideoSearchRequest` → `VideoSearchResponse` | `IVideoSearchClient.search_videos` |

Every MCP tool follows the same template:

```text
receive raw args → Pydantic validate → call application → Pydantic validate response → return
```

---

### 4. Infrastructure (`src/mcp_server/infrastructure/`)

Concrete adapters. The only layer that imports Supabase, DuckDuckGo, YouTube, and Redis clients.

| Adapter | Port | Agentic capability | Status |
| :--- | :--- | :--- | :--- |
| `tavily_search_client.py` | `ISearchClient` | Tavily API → normalized `list[str]` snippets | ✅ Live |
| `search_client.py` | `ISearchClient` | DuckDuckGo fallback when `TAVILY_API_KEY` unset | Stub |
| `youtube_client.py` | `IVideoSearchClient` | YouTube Data API v3 → `list[VideoResult]` | ✅ Live |
| `cached_adapters.py` | wraps above | Cache-aside for repeated agent tool calls | ✅ |
| `cached_llm.py` | wraps `BaseChatModel` | Cache-aside for LLM completions (**async path only**) | ✅ |
| `groq_adapter.py` | — | Groq `ChatGroq` builder for `LLMRouter` | ✅ |
| `mcp_tool_cache.py` | — | Optional MCP tool I/O caching at the interface boundary | ✅ |

#### Web search (`ISearchClient`)

- Input: `query`, `max_results` (validated, capped).
- Output: `list[str]` snippets — title, content excerpt, and URL joined per result (not raw provider JSON).
- **Primary adapter:** `TavilySearchClient` when `TAVILY_API_KEY` is set in Settings.
- **Fallback:** `DuckDuckGoSearchClient` when Tavily key is absent (still a stub — returns `NotImplementedError` after guards).

**Wiring:**

```text
wiring.build_search_client(settings, cache)
  → TavilySearchClient (if TAVILY_API_KEY) else DuckDuckGoSearchClient
  → optional CachedSearchClient wrapper
  → integration_runtime.get_search_client()  (lazy, wired at bootstrap)
  → agents/tavily_search, agents/research_article tool nodes
```

`configure_lazy_integration_clients(settings, cache)` is called from `initialize_application_runtime()` alongside the chat model. Search and video clients are consumed by the research-article agent graph and any MCP tool.

#### LLM completion cache (`CachedChatModel`)

`CachedChatModel` wraps the chat model built by `application/llm.py` at the composition root (`wiring.py`). It applies cache-aside on **`_agenerate` only** (the path used by `ainvoke` and LangGraph async nodes). The sync `_generate` method delegates to the inner model without cache lookup or store.

| Path | Cached? | When used |
| :--- | :--- | :--- |
| `_agenerate` / `ainvoke` | Yes (when `CACHE_ENABLED` and rule enabled) | LangGraph agents, async workflows |
| `_generate` / `invoke` | No — always calls provider | No current production callers; sync cache deferred |

TTL and key prefix: `CACHE_TTL_LLM_COMPLETION`, `CACHE_KEY_PREFIX_LLM` (see env table below).

#### YouTube search (`IVideoSearchClient`)

- Input: `query`, `max_results`, `language`, `safe_search` (see `VideoSearchRequest` in `validation.py`).
- Output: `list[VideoResult]` — title, channel, canonical `watch?v=` URL.
- **Adapter:** `YouTubeDataApiClient` — live YouTube Data API v3 via `asyncio.to_thread` around the Google client.
- Wired through `build_video_client()` → `integration_runtime.get_video_client()`.
- Used by MCP `search_youtube`, `agents/youtube_search`, and `agents/research_article` (`tool_search_youtube` node).

---

### 5. Entrypoint (`main.py`, `settings.py`, `wiring.py`)

Composition root and transport bootstrap.

| Concern | Where |
| :--- | :--- |
| Load secrets / Settings | `settings.py`, `main.py` (`bootstrap_environment`) |
| Wire ports → workflows → agents | `wiring.py` |
| Start MCP transport | `main.py` → `create_mcp_server().run()` |

#### `wiring.py` responsibilities

```text
build_search_client(settings, cache)       → ISearchClient (Tavily preferred)
build_video_client(settings, cache)        → IVideoSearchClient (YouTube live)
build_chat_model(settings, cache)          → BaseChatModel (Groq router + optional cache)
configure_lazy_integration_clients(...)    → search + video client lazy builders
configure_lazy_chat_model(...)             → chat model lazy builder
```

`main()` calls `initialize_application_runtime()` so all lazy builders are registered before MCP tools execute.

---

## Capability flows

### A. Find documents (backend RAG, not an MCP tool)

Document RAG lives in `ed-tech-system-backend`:

```text
PraxisWeb → POST /functions/v1/mcp-find-documents
  → tenant membership check
  → embed query via backend embedding service (FastEmbed / E5)
  → Supabase hybrid_search_chunks RPC
  → list[EnrichmentDocument]
  → PraxisWeb panel
```

The MCP server only provides `build_lesson_enrichment_query`, which expands lesson metadata into 4–5 search terms that the frontend can pass to the backend document search and YouTube search.

### B. Search the web (planned MCP tool)

```text
MCP: search_web(query, max_results?)
  → WebSearchRequest validation
  → LangChain tool search_web OR direct workflow step
  → ISearchClient.search(query, max_results)
  → TavilySearchClient or DuckDuckGoSearchClient
  → WebSearchResponse validation
  → MCP client
```

### C. Search YouTube videos

```text
MCP: search_youtube(query, max_results?, language?, safe_search?)
  → VideoSearchRequest validation (existing schema)
  → IVideoSearchClient.search_videos(...)
  → YouTubeDataApiClient
  → VideoSearchResponse validation
  → MCP client
```

### D. Research → journalistic article

```text
MCP or scripted agent: research_article(query, max_web_results?, max_video_results?)
  → ResearchArticleRunRequest validation
  → get_research_article_graph()
      agent_plan_research   → LLM editorial brief (Groq, MEDIUM complexity)
      dispatch_parallel_tools → LangGraph Send fan-out
          tool_search_tavily   → ISearchClient (async node)
          tool_search_youtube  → IVideoSearchClient (async node)
      merge_context         → defer=True; waits for both tools; builds merged_context + tool_calls
      write_article         → LLM journalistic output (Groq, HIGH complexity)
  → ResearchArticleRunResponse (brief, sources, article, trace)
```

### E. Lesson → quiz + PBL

```text
MCP or scripted agent: content_generation(topic, grade_level?)
  → ContentGenerationRunRequest validation
  → get_content_generation_graph()
      generate_lesson ⇄ validate_lesson (retry loop)
      generate_quiz   ⇄ validate_quiz
      generate_pbl    ⇄ validate_pbl
      merge_results
  → ContentGenerationRunResponse (lesson, quiz, pbl, retry counts, trace)
```

- **LLM:** Groq via `RoutingChatModel` → `LLMRouter` with complexity tiers, **per-complexity debounce**, and **capped fallback** (`LLM_ROUTER_MAX_FALLBACKS`, default one extra model) on provider failure.
- **Validation retries:** `config.json` `validation_retries` (separate from provider `node_retries`); failed Pydantic/JSON parses loop back to `generate_*` nodes.
- **Trace:** each LLM node records `llm_io` (system/user prompts, raw output, `model_name`, `llm_complexity`) via `workflow_llm_trace`.

---

## Validation schema map

| Schema | Layer file | Used by |
| :--- | :--- | :--- |
| `VideoSearchRequest` / `VideoSearchResponse` | `interface/validation.py` | MCP `search_youtube` |
| `BuildLessonEnrichmentQueryRequest` / `BuildLessonEnrichmentQueryResponse` | `interface/validation.py` | MCP `build_lesson_enrichment_query` |
| `TavilySearchRunRequest` / `TavilySearchRunResponse` | `interface/validation_workflow.py` | Scripted Tavily workflow runs |
| `YouTubeSearchRunRequest` / `YouTubeSearchRunResponse` | `interface/validation_workflow.py` | Scripted YouTube workflow runs |
| `ResearchArticleRunRequest` / `ResearchArticleRunResponse` | `interface/validation_workflow.py` | Research article agent |
| `ContentGenerationRunRequest` / `ContentGenerationRunResponse` | `interface/validation_workflow.py` | Content generation agent |
| `WorkflowTraceStepView` | `interface/validation_workflow.py` | Trace replay in all workflow responses |
| `WebSearchRequest` / `WebSearchResponse` *(planned)* | `interface/validation.py` | MCP `search_web` |
| `VideoResult` | `domain/schemas.py` | Video search domain boundary |

---

## LangGraph agent design

### Registered workflows

`list_registered_workflows()` in `agent.py` exposes compiled graphs for introspection and scripted tests. As of 2026-08-24:

| Workflow ID | Package | Graph shape | External deps |
| :--- | :--- | :--- | :--- |
| `tavily-search` | `agents/tavily_search/` | `search_web` | `TAVILY_API_KEY` |
| `youtube-search` | `agents/youtube_search/` | `search_videos` | `YOUTUBE_API_KEY` |
| `research-article` | `agents/research_article/` | plan → **parallel tools** → merge → write | Tavily + YouTube + `GROQ_API_KEY` |
| `content-generation` | `agents/content_generation/` | lesson/quiz/pbl with validation retries | `GROQ_API_KEY` |
| `course-scaffold` | `agents/course_scaffold/` | structure-only `{ nodes, edges }` (no lesson bodies) | `GROQ_API_KEY` |
| `project-review` | `agents/project_review/` | collect context → grade + validate | `GROQ_API_KEY` + Supabase |
| `socratic-tutor` | `agents/socratic/` | hint-ladder tutoring grounded in backend catalog | `GROQ_API_KEY` |

MCP production tools are `health_check`, `search_youtube`, and `build_lesson_enrichment_query`. Document RAG is handled by the backend embedding service; the MCP does not run `find_documents` or host `rag_retrieval` workflows.

See [OBSERVABILITY.md](./OBSERVABILITY.md) for trace fields, replay controls, run summary, and edge highlighting semantics.

### Homologation status

Core workflow graph tests are covered by pytest. Live-key homologation (`RUN_SECRETS_HOMOLOGATION=1`) validates Tavily, YouTube, and Groq credentials.

### Parallel async tool nodes (`research-article`)

LangGraph `Send` fan-out dispatches two tool nodes after planning:

```text
agent_plan_research
        ├─(async)─► tool_search_tavily  ──┐
        └─(async)─► tool_search_youtube ──┴─► merge_context (defer=True) → write_article
```

- `dispatch_parallel_tools` returns `[Send("tool_search_tavily", state), Send("tool_search_youtube", state)]`.
- `merge_context` uses `defer=True` so it runs **once** after both branches complete.
- Each tool node records its own `ToolCallRecord` (`search_tavily` / `search_youtube`) in state; `merge_context` assembles `tool_calls` and `merged_context`.
- Graph layout places tool nodes on a parallel branch (Tavily above, YouTube below) with purple **`async`** edges.

### State

Each graph defines a `TypedDict` state (e.g. `TavilySearchState` in `agents/tavily_search/`). State fields are:

- **Inputs** — user query, limits, flags
- **Intermediate** — tool outputs, derived search terms
- **Outputs** — merged results, counts, error markers

State is the **only** shared memory between nodes. Nodes return partial state updates as `dict` fragments.

### Nodes

| Node type | Calls | Example |
| :--- | :--- | :--- |
| **Tool** | Domain port via `integration_runtime` | `tool_search_tavily`, `search_web` |
| **LLM** | `get_chat_model()` + trace capture | `agent_plan_research`, `generate_lesson`, `write_article` |
| **Merge** | Pure Python on state | `merge_context`, `merge_results` |
| **Route** | Conditional edge or `Send` fan-out | `dispatch_parallel_tools`, `_route_after_validate_*` |

---

## Agent file structure

The tree below is the **canonical layout** for runtime agents, LangGraph workflows, and related wiring. It extends the base layout in [ARCHITECTURE.md](./ARCHITECTURE.md) with agent-specific modules.

**Legend:** ✅ exists today · 📋 planned (named in this doc, not yet on disk)

```text
ed-tech-system-mcp/
│
├── AGENTIC_ARCHITECTURE.md              # This document
├── ARCHITECTURE.md                      # Layer boundaries and core patterns
├── config.json                          # ✅ Operational tuning (retries, workflow timeouts)
│
├── tests/
│   ├── test_agent.py                    # ✅ Workflow registry + memoization
│   ├── test_workflow_graph.py           # ✅ Layout + async edge classification
│   ├── test_workflow_trace.py           # ✅ Trace status, retries, LLM I/O
│   ├── test_research_article_graph.py   # ✅ Parallel tools + article generation
│   ├── test_content_generation_graph.py # ✅ Lesson/quiz/PBL + router fallback
│   ├── test_integration_clients.py      # ✅ Tavily + YouTube adapter unit tests
│   └── test_llm.py                      # ✅ Groq router, fallback, cache
│
└── src/
    └── mcp_server/
        │
        ├── main.py                      # ✅ MCP entrypoint — bootstrap, settings, server.run()
        ├── settings.py                  # ✅ Typed config (Groq, Tavily, YouTube, cache)
        ├── operational_config.py        # ✅ Pydantic loader for repo-root config.json
        ├── wiring.py                    # ✅ Composition root — ports, workflows, cache, lazy builders
        │
        ├── domain/                      # Pure contracts — no LangChain / MCP / SDKs
        │   ├── interfaces.py            # ✅ ISearchClient, IVideoSearchClient, authoring ports
        │   ├── schemas.py               # ✅ VideoResult, graph entities/relations
        │   ├── content_schemas.py     # ✅ Lesson/quiz/PBL draft contracts
        │   ├── cache.py                 # ✅ ICacheStore port
        │   ├── cache_keys.py            # ✅ Deterministic cache key builders
        │   └── exceptions.py            # ✅ Domain errors → interface mapping
        │
        ├── application/                 # Agents, graphs, LangChain tools, orchestration
        │   ├── agent.py                 # ✅ Workflow registry
        │   ├── integration_runtime.py   # ✅ Lazy ISearchClient / IVideoSearchClient accessors
        │   ├── workflow_trace.py        # ✅ Per-node execution trace collection
        │   ├── workflow_llm_trace.py    # ✅ LLM prompt/output capture per node
        │   ├── workflow_graph.py        # ✅ Graph introspection + layout (async edges)
        │   ├── workflow_config.py       # ✅ WorkflowExecutionConfig runtime view
        │   ├── llm_router.py            # ✅ Groq capped fallback + per-complexity debounce
        │   ├── routing_chat_model.py    # ✅ LangChain adapter over LLMRouter
        │   ├── llm_models.py            # ✅ Groq model registry from catalog
        │   ├── llm.py                   # ✅ create_chat_model(settings) → BaseChatModel
        │   ├── parameter_builders.py    # 📋 Rule + state + optional LLM param builders
        │   ├── langchain_tools.py       # 📋 @tool wrappers (web, youtube)
        │   │
        │   └── agents/                  # ✅ One package per LangGraph workflow
        │       ├── content_generation/  #     Lesson → quiz + PBL (validation retries)
        │       ├── course_scaffold/     #     Structure-only course graph proposal
        │       ├── research_article/    #     Plan → parallel Tavily/YouTube → article
        │       ├── tavily_search/       #     Single-node Tavily integration test
        │       ├── youtube_search/      #     Single-node YouTube integration test
        │       ├── project_review/      #     Project delivery grading + feedback
        │       └── socratic/            #     Backend-grounded Socratic tutor
        │
        ├── interface/                   # MCP protocol adapters
        │   ├── mcp_server.py            # ✅ FastMCP instance
        │   ├── custom_tools.py          # ✅ health_check, search_youtube, build_lesson_enrichment_query
        │   ├── validation.py            # ✅ All MCP request/response models
        │   └── validation_workflow.py   # ✅ Workflow run schemas for scripted tests
        │
        └── infrastructure/              # Provider adapters — only layer with external SDKs
            ├── tavily_search_client.py  # ✅ ISearchClient — Tavily HTTP API
            ├── search_client.py         # ✅ ISearchClient — DuckDuckGo fallback (stub)
            ├── youtube_client.py        # ✅ IVideoSearchClient — YouTube Data API v3
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
| `application/agent.py` | Application | Workflow registry (`list_registered_workflows`) |
| `interface/custom_tools.py` | Interface | MCP tool surface — validate in, delegate out |
| `interface/validation.py` | Interface | All MCP request/response Pydantic models |
| `wiring.py` | Entrypoint | Wire ports → LangChain tools → graphs → MCP tool handlers |

### Growth path: packaged agents

New workflows follow the packaged layout:

1. **Graph package** under `application/agents/<name>/` (`state.py`, `nodes.py`, `graph.py`, optional `prompts.py`).
2. **Registration** in `list_registered_workflows()` for introspection and tests.
3. **Tests** under `tests/test_<name>_graph.py` and layout contracts in `tests/test_workflow_graph.py`.
4. **UI spine + edges** in `workflow_graph._WORKFLOW_SPINES` / `_WORKFLOW_EDGES` when LangGraph drawable edges are incomplete (e.g. `Send` fan-out).

**Next packaged agents (planned):** `web_enrich/`. MCP `search_web` should delegate through a LangChain tool once `langchain_tools.py` ships.

---

## Settings and secrets (agentic extensions)

Extend `Settings` in `settings.py`:

| Variable | Used by |
| :--- | :--- |
| `GROQ_API_KEY` | `application/llm.py` via `LLMRouter` |
| `LLM_TEMPERATURE`, `LLM_COMPLEXITY` | Chat sampling + default complexity tier; **model ids** come from `list_active_groq_models` (not `LLM_MODEL`) |
| `TAVILY_API_KEY` | `TavilySearchClient` via `build_search_client()` |
| `YOUTUBE_API_KEY` | `YouTubeDataApiClient` via `build_video_client()` |
| `CACHE_TTL_*`, `CACHE_KEY_PREFIX_*` | Cache-aside for LLM, YouTube, Tavily, MCP tools |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Authoring, project review, Socratic catalog |
| `CACHE_ENABLED`, `REDIS_URL` | Optional Redis cache for LLM/tool I/O |

All keys are `SecretStr`, loaded at entrypoint, injected via `wiring.py`. Never embedded in LangChain prompts or tool descriptions.

---

## Anti-patterns (agentic)

| Anti-pattern | Why it fails |
| :--- | :--- |
| MCP tool calls LangChain agent internally, agent calls same MCP tool | Infinite recursion; protocol leak |
| Parameter builder returns unvalidated dict to infrastructure | Hallucinated filters crash adapters |
| LangChain tool imports `supabase` or `googleapiclient` | Breaks Clean Architecture |
| Global chat model singleton with lazy env read | Untestable; breaks CI without keys |
| Returning raw Supabase / YouTube / DDG payloads to MCP client | Token waste; schema boundary violation |

---

## File map (quick reference)

| Path | Status | Agentic role |
| :--- | :--- | :--- |
| `application/agent.py` | ✅ | Workflow registry |
| `application/agents/` | ✅ | `content_generation`, `course_scaffold`, `research_article`, `tavily_search`, `youtube_search`, `project_review`, `socratic` |
| `application/integration_runtime.py` | ✅ | Lazy Tavily/YouTube client accessors |
| `application/workflow_trace.py` | ✅ | Execution trace collection |
| `application/workflow_llm_trace.py` | ✅ | Per-node LLM I/O for observability |
| `application/workflow_graph.py` | ✅ | Graph layout, async/retry edge kinds |
| `application/llm_router.py` | ✅ | Groq capped fallback + per-complexity debounce |
| `application/langchain_tools.py` | 📋 | LangChain `@tool` wrappers |
| `interface/custom_tools.py` | ✅ | MCP: `health_check`, `search_youtube`, `build_lesson_enrichment_query` |
| `interface/validation.py` | ✅ | MCP DTOs |
| `interface/validation_workflow.py` | ✅ | Scripted workflow run DTOs |
| `domain/interfaces.py` | ✅ | `ISearchClient`, `IVideoSearchClient`, authoring ports |
| `domain/schemas.py` | ✅ | `VideoResult`, graph entities/relations |
| `infrastructure/tavily_search_client.py` | ✅ | Tavily HTTP adapter |
| `infrastructure/youtube_client.py` | ✅ | YouTube Data API v3 adapter |
| `wiring.py` | ✅ | Composition root + DI |
| `settings.py` | ✅ | Typed secrets + operational aliases |
