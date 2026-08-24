# Agentic Architecture: LangChain, LangGraph, and MCP Tool Orchestration

This document extends [ARCHITECTURE.md](./ARCHITECTURE.md). It defines how **language models**, **agents**, **tools**, and **data/search capabilities** are coupled inside the ed-tech MCP server.

`ARCHITECTURE.md` defines *where* code lives and *which dependencies are allowed per layer*. This document defines *how agentic execution flows* across those layers: LLM access, conditional parameter construction, tool invocation, and retrieval from Supabase, the web, and YouTube.

---

## Relationship to `ARCHITECTURE.md`

| Document | Scope |
| :--- | :--- |
| **ARCHITECTURE.md** | Clean Architecture layers, ports & adapters, validation boundaries, anti-patterns |
| **AGENTIC_ARCHITECTURE.md** | Agent graphs, LLM wiring, tool taxonomy, capability flows (DB / web / video), conditional parameters |
| **[OBSERVABILITY.md](./OBSERVABILITY.md)** | Local workflow UI, execution trace/replay, LLM I/O inspection, debugging |

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
│  INFRASTRUCTURE — supabase_client · tavily_search_client · search_client   │
│  • youtube_client · cached_adapters · groq_adapter                         │
│  • Supabase repository (structured queries)                                │
│  • Tavily web search (preferred) · DuckDuckGo fallback (stub)              │
│  • YouTube Data API v3 (live)                                              │
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
| `agent.py` | LangGraph graph definitions, `list_registered_workflows()` for local UI |
| `integration_runtime.py` | Lazy accessors for `ISearchClient` and `IVideoSearchClient` (Tavily / YouTube) |
| `workflow_trace.py` | `invoke_graph_with_trace()` — per-node replay for local UI |
| `workflow_llm_trace.py` | Captures LLM prompts, raw output, and model name per node |
| `llm.py` / `llm_router.py` | `create_chat_model()`, Groq `LLMRouter` with per-complexity debounce and capped model fallback |
| `workflow_graph.py` | Graph introspection DTOs, spine layout, async/retry edge classification for UI |
| `agents/*/` | One package per LangGraph workflow (`content_generation`, `research_article`, `tavily_search`, `youtube_search`) |
| `langchain_tools.py` *(planned)* | `@tool` wrappers: `search_web`, `search_youtube`, `run_sql_read` |
| `parameter_builders.py` *(planned)* | Build tool/agent parameters from graph state, user intent, and prior retrieval results |

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
| User provides explicit filters (course_id, tags) | Structured repository `find_documents` with validated parameters |

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
| `build_lesson_enrichment_query` | ✅ | `BuildLessonEnrichmentQueryRequest` | Lightweight LLM term expansion |
| `search_youtube` | ✅ | `VideoSearchRequest` → `VideoSearchResponse` | `IVideoSearchClient.search_videos` |
| `search_web` | 📋 planned | `WebSearchRequest` → `WebSearchResponse` | web search LangChain tool / workflow |
| `rag_search` | 📋 planned | `RagSearchRequest` → `RagSearchResponse` | `rag_retrieval` LangGraph via `retrieval_runtime` |
| `query_supabase_sql` | 📋 planned | `SqlAgentRequest` → `SqlAgentResponse` | SQL agent subgraph (read-only) |

Every MCP tool follows the same template:

```text
receive raw args → Pydantic validate → call application → Pydantic validate response → return
```

---

### 4. Infrastructure (`src/mcp_server/infrastructure/`)

Concrete adapters. The only layer that imports Supabase, DuckDuckGo, YouTube, and Redis clients.

| Adapter | Port | Agentic capability | Status |
| :--- | :--- | :--- | :--- |
| `supabase_client.py` | `IDataRepository` | Structured document retrieval | Stub (guards live; HTTP body deferred BL-022) |
| `supabase_sql_executor.py` *(planned)* | `ISqlReadExecutor` | Execute **validated** read-only SQL | 📋 Planned |
| `tavily_search_client.py` | `ISearchClient` | Tavily API → normalized `list[str]` snippets | ✅ Live |
| `search_client.py` | `ISearchClient` | DuckDuckGo fallback when `TAVILY_API_KEY` unset | Stub |
| `youtube_client.py` | `IVideoSearchClient` | YouTube Data API v3 → `list[VideoResult]` | ✅ Live |
| `cached_adapters.py` | wraps above | Cache-aside for repeated agent tool calls | ✅ |
| `cached_llm.py` | wraps `BaseChatModel` | Cache-aside for LLM completions (**async path only**) | ✅ |
| `groq_adapter.py` | — | Groq `ChatGroq` builder for `LLMRouter` | ✅ |
| `mcp_tool_cache.py` | — | Optional MCP tool I/O caching at the interface boundary | ✅ |

#### Supabase — structured queries (`IDataRepository`)

Infrastructure implements `find_documents` using **explicit, parameterized** Supabase operations:

- Full-text or `ilike` search on `query`
- Optional filters: `course_id`, `topic_tags`, `language`, `published_after`
- `limit` / `offset` enforced at validation and again in the adapter (defense in depth)

The LLM never constructs raw PostgREST URLs. It may only populate fields on a validated request model, which maps to a fixed query template in the adapter.

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
- Output: `list[str]` snippets — title, content excerpt, and URL joined per result (not raw provider JSON).
- **Primary adapter:** `TavilySearchClient` when `TAVILY_API_KEY` is set in Settings.
- **Fallback:** `DuckDuckGoSearchClient` when Tavily key is absent (still a stub — returns `NotImplementedError` after guards).

**Wiring (finalized 2026-07-22):**

```text
wiring.build_search_client(settings, cache)
  → TavilySearchClient (if TAVILY_API_KEY) else DuckDuckGoSearchClient
  → optional CachedSearchClient wrapper
  → integration_runtime.get_search_client()  (lazy, wired at bootstrap)
  → agents/tavily_search, agents/research_article tool nodes
```

`configure_lazy_integration_clients(settings, cache)` is called from `initialize_application_runtime()` alongside the chat model. Search and video clients are consumed by dedicated UI workflows and the research-article agent graph.

MCP `search_web` and `application/langchain_tools.py` remain **planned** — the live path today is LangGraph nodes calling ports via `integration_runtime`.

#### LLM completion cache (`CachedChatModel`)

`CachedChatModel` wraps the chat model built by `application/llm.py` at the composition root (`wiring.py`). It applies cache-aside on **`_agenerate` only** (the path used by `ainvoke` and LangGraph async nodes). The sync `_generate` method delegates to the inner model without cache lookup or store.

| Path | Cached? | When used |
| :--- | :--- | :--- |
| `_agenerate` / `ainvoke` | Yes (when `CACHE_ENABLED` and rule enabled) | LangGraph agents, async workflows |
| `_generate` / `invoke` | No — always calls provider | No current production callers; sync cache deferred |

TTL and key prefix: `CACHE_TTL_LLM_COMPLETION`, `CACHE_KEY_PREFIX_LLM` (see env table below).

#### RAG retrieval cache boundary

| Cache type | MCP layer (this service) | Backend (Supabase) |
| :--- | :--- | :--- |
| ONNX model **weights** | ✅ `EMBEDDING_CACHE_DIR` (Docker image bake on Render) | — |
| Query embedding **vectors** (Redis) | ❌ disabled in `wiring.py` | — |
| Chunk / document **hits** (Redis) | ❌ disabled in `wiring.py` | Fresh reads via `match_chunks` / `hybrid_search_chunks` |

`CACHE_TTL_EMBEDDING_QUERY` and `CACHE_TTL_VECTOR_RETRIEVE` exist in settings for adapter tests only; production wiring never Redis-wraps `IEmbeddingProvider`, `IVectorRetriever`, or `find_documents`.

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
| Local workflow UI | `local_ui_main.py` (development only) |

#### `wiring.py` responsibilities

```text
build_search_client(settings, cache)       → ISearchClient (Tavily preferred)
build_video_client(settings, cache)        → IVideoSearchClient (YouTube live)
build_chat_model(settings, cache)          → BaseChatModel (Groq router + optional cache)
configure_lazy_integration_clients(...)    → search + video client lazy builders
configure_lazy_chat_model(...)             → chat model lazy builder
```

`main()` and the local UI lifespan call `initialize_application_runtime()` so all lazy builders are registered before MCP tools or UI workflow runs execute.

---

## Capability flows

### A. Find documents (backend RAG, not an MCP tool)

Document RAG moved to the backend:

```text
PraxisWeb → POST /functions/v1/mcp-find-documents
  → tenant membership check
  → embed query via backend embedding service (FastEmbed / E5)
  → Supabase hybrid_search_chunks RPC
  → list[EnrichmentDocument]
  → PraxisWeb panel
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
  → IVideoSearchClient.search_videos(...)
  → YouTubeDataApiClient
  → VideoSearchResponse validation
  → MCP client
```

### E. Tavily web search (local UI workflow)

```text
UI: POST /api/workflows/tavily-search/run { query, max_results }
  → TavilySearchRunRequest validation
  → get_tavily_search_graph() — single-node graph
      search_web → ISearchClient.search() via integration_runtime
  → TavilySearchRunResponse (results + execution trace)
```

Requires `TAVILY_API_KEY`. Returns `503` when the search client is not wired.

### G. YouTube video search (local UI workflow)

```text
UI: POST /api/workflows/youtube-search/run { query, max_results, language?, safe_search? }
  → YouTubeSearchRunRequest validation
  → get_youtube_search_graph() — single-node graph
      search_videos → IVideoSearchClient.search_videos() via integration_runtime
  → YouTubeSearchRunResponse (videos + execution trace)
```

Requires `YOUTUBE_API_KEY`. Homologated in `tests/test_secrets_homologation.py` (`test_h04`).

### H. Research → journalistic article (local UI workflow)

```text
UI: POST /api/workflows/research-article/run { query, max_web_results?, max_video_results? }
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

Parallel tool nodes are **separate LangGraph nodes** (not hidden inside one orchestrator) so the workflow UI can visualize the async fork and record per-tool trace steps. Graph edges from `Send` fan-out are declared explicitly in `workflow_graph._WORKFLOW_EDGES` because LangGraph's drawable graph omits them.

### I. Lesson → quiz + PBL (local UI workflow)

```text
UI: POST /api/workflows/content-generation/run { topic, grade_level? }
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

### J. Semantic RAG retrieval (Phase A — shipped)

See [INVESTIGATION1.md](changelog/2026-07-22/domain/INVESTIGATION1.md) for library selection, ports, and ingest pipeline.

```text
UI: POST /api/workflows/rag-retrieval/run { query, retrieval_mode?, course_id?, tags? }
  → RagRetrievalRunRequest validation
  → get_rag_retrieval_graph()
      embed_query      → IEmbeddingProvider.embed_queries via retrieval_runtime
      retrieve_chunks  → IVectorRetriever (hybrid default)
      [rerank_chunks?] → IReranker (RERANK_ENABLED)
      merge_context
  → RagRetrievalRunResponse (chunks, merged_context, trace)
```

- **Embeddings:** local `fastembed` ONNX (`intfloat/multilingual-e5-small`); Groq has no embeddings API.
- **Vector store:** Supabase pgvector + hybrid RPC; structured `IDataRepository` and semantic `IVectorRetriever` may run in parallel (BL-010 pattern).
- **Rerank:** optional (`RERANK_ENABLED=false` MVP default); when enabled use `BAAI/bge-reranker-base` via fastembed — not Jina v2 (CC-BY-NC).
- **Trace:** RAG nodes record `candidate_count`, `cache_hit`, `retrieval_mode`, `latency_ms` in `output_update` — not `llm_io`.

---

## Validation schema map

| Schema | Layer file | Used by |
| :--- | :--- | :--- |
| `VideoSearchRequest` / `VideoSearchResponse` | `interface/validation.py` | MCP `search_youtube` |
| `BuildLessonEnrichmentQueryRequest` / `BuildLessonEnrichmentQueryResponse` | `interface/validation.py` | MCP `build_lesson_enrichment_query` |
| `TavilySearchRunRequest` / `TavilySearchRunResponse` | `interface/validation.py` | Local UI `tavily-search` |
| `YouTubeSearchRunRequest` / `YouTubeSearchRunResponse` | `interface/validation.py` | Local UI `youtube-search` |
| `ResearchArticleRunRequest` / `ResearchArticleRunResponse` | `interface/validation.py` | Local UI `research-article` |
| `ContentGenerationRunRequest` / `ContentGenerationRunResponse` | `interface/validation.py` | Local UI `content-generation` |
| `RagRetrievalRunRequest` / `RagRetrievalRunResponse` | `interface/validation.py` | Local UI `rag-retrieval` |
| `WorkflowTraceStepView` | `interface/validation.py` | Trace replay in all UI workflow responses |
| `WebSearchRequest` / `WebSearchResponse` *(planned)* | `interface/validation.py` | MCP `search_web` |
| `SqlAgentRequest` / `SqlAgentResponse` *(planned)* | `interface/validation.py` | MCP `query_supabase_sql` |
| `SqlQueryProposal` *(planned)* | `domain/schemas.py` or `validation.py` | LLM → SQL agent gate |
| `DocumentHit`, `VideoResult` | `domain/schemas.py` | Internal entity boundary |

---

## LangGraph agent design

### Registered workflows (local UI)

`list_registered_workflows()` in `agent.py` exposes compiled graphs to the local workflow explorer. As of 2026-07-22:

| Workflow ID | Package | Graph shape | External deps |
| :--- | :--- | :--- | :--- |
| `tavily-search` | `agents/tavily_search/` | `search_web` | `TAVILY_API_KEY` |
| `youtube-search` | `agents/youtube_search/` | `search_videos` | `YOUTUBE_API_KEY` |
| `research-article` | `agents/research_article/` | plan → **parallel tools** → merge → write | Tavily + YouTube + `GROQ_API_KEY` |
| `content-generation` | `agents/content_generation/` | lesson/quiz/pbl with validation retries | `GROQ_API_KEY` |
| `rag-retrieval` | `agents/rag_retrieval/` | embed → retrieve → [rerank?] → merge | `fastembed` + Supabase |

MCP production tools no longer include `find_documents` or `run_workflow`; document RAG moved to the backend embedding service. The MCP still exposes `health_check`, `search_youtube`, and `build_lesson_enrichment_query`. The local UI favors focused integration-test workflows plus the full agentic paths above.

See [OBSERVABILITY.md](./OBSERVABILITY.md) for trace fields, replay controls, run summary, and edge highlighting semantics.

### Homologation status (2026-07-22)

All four local UI workflows are covered by pytest and pass in CI (`206 passed`). Live-key homologation (`RUN_SECRETS_HOMOLOGATION=1`) validates Tavily, YouTube, and Groq credentials.

| Behavior | How to verify |
| :--- | :--- |
| Tavily + YouTube integrations | `tavily-search`, `youtube-search`, `research-article` UI runs |
| Parallel async tool trace | `research-article` replay shows `tool_search_tavily` and `tool_search_youtube` as separate steps |
| Validation retries | `content-generation` with bad LLM output — see `tests/test_workflow_trace.py` |
| Groq model fallback | `LLMRouter` tries one extra model by default — `test_llm14_router_falls_back_on_provider_failure`, `test_llm14b_router_caps_fallback_attempts` |

**Note:** Fallback and retry paths do not appear in the UI unless a node actually fails. Clean runs show all-green traces. To exercise fallbacks locally, use the scripted tests above or temporarily misconfigure a model tier in tests.

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
- UI layout places tool nodes on a parallel branch (Tavily above, YouTube below) with purple **`async`** edges.

### State

Each graph defines a `TypedDict` state (e.g. `TavilySearchState` in `agents/tavily_search/`). State fields are:

- **Inputs** — user query, limits, flags
- **Intermediate** — retrieved documents, derived search terms, tool outputs
- **Outputs** — merged results, counts, error markers

State is the **only** shared memory between nodes. Nodes return partial state updates as `dict` fragments.

### Nodes

| Node type | Calls | Example |
| :--- | :--- | :--- |
| **Retrieval** | Domain port via injected dependency | `fetch_documents` |
| **Transform** | Parameter builder (rules / LLM) | `derive_search_terms` |
| **Tool** | Domain port via `integration_runtime` | `tool_search_tavily`, `search_web` |
| **LLM** | `get_chat_model()` + trace capture | `agent_plan_research`, `generate_lesson`, `write_article` |
| **Merge** | Pure Python on state | `merge_context`, `merge_results` |
| **Route** | Conditional edge or `Send` fan-out | `dispatch_parallel_tools`, `_route_after_validate_*` |

### Graph registration

`list_registered_workflows()` memoizes compiled graphs for the local workflow UI. MCP exposure uses dedicated tools; workflow packages under `agents/` are the single source of graph definitions.

---

## Local Workflow UI (finalized)

The workflow explorer is **development-only** (`local_ui_main.py`, loopback bind). It is the primary surface for homologating integrations and agent graphs before MCP exposure.

### Stack

| Layer | Path | Role |
| :--- | :--- | :--- |
| API | `interface/local_ui/api.py` | `GET /api/workflows`, `POST /api/workflows/{id}/run` |
| Graph DTOs | `application/workflow_graph.py` | Node positions, edge kinds (`forward`, `retry`, `failure`, `async`) |
| Trace | `application/workflow_trace.py` | `invoke_graph_with_trace()` via `stream_mode="updates"` |
| UI | `ui/src/` | React Flow graph, run panel, step replay, LLM I/O inspector |

Start with `./scripts/dev/run-workflow-ui.sh` → http://127.0.0.1:4173 (API on :8877).

### UI capabilities

| Feature | Component | Behavior |
| :--- | :--- | :--- |
| Workflow sidebar | `App.tsx` | Lists all `list_registered_workflows()` entries |
| Graph canvas | `WorkflowGraphView.tsx` | Custom nodes, handles, traversed-path highlighting, async/retry edge styles |
| Run panel | `WorkflowRunPanel.tsx` | Per-workflow forms (query, limits, topic/grade) |
| Run summary | `WorkflowRunSummary.tsx` | Step counts, retry/failed stats, `generation_complete` warning |
| Step replay | `WorkflowTraceReplay.tsx` | Auto-advances to last step; click steps to inspect |
| LLM inspector | `WorkflowStepInspector.tsx` | `input_snapshot`, `output_update`, `llm_io` per step |

### Edge kinds in the canvas

| Kind | Visual | Used for |
| :--- | :--- | :--- |
| `forward` | Solid blue | Normal sequential execution |
| `async` | Dashed purple, label `async` | Parallel fan-out (`research-article` tool branches) |
| `retry` | Dashed amber, label `retry` | Validation retry loops (`content-generation`) |
| `failure` | Dashed red, label `give up` | Exhausted retries → early merge |

### Bootstrap behavior

- **Graph browsing** works without secrets (structure-only API).
- **Execution** requires wired runtime: FastAPI lifespan calls `bootstrap_application_runtime()`. Missing credentials return `503` with a clear message.
- Live integration tests: `tests/interface/test_local_ui_api.py` (Tavily/YouTube when keys present); `tests/test_research_article_graph.py` (scripted LLM + fake ports).

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
│       ├── App.tsx                      # Workflow list + run summary + replay shell
│       ├── api/workflows.ts             # Workflow + trace TypeScript types
│       ├── lib/traceAnalytics.ts        # Path/edge analytics for graph highlighting
│       └── components/
│           ├── WorkflowGraphView.tsx    # React Flow graph (forward/async/retry edges)
│           ├── WorkflowRunPanel.tsx     # Per-workflow run forms
│           ├── WorkflowRunSummary.tsx   # Post-run stats banner
│           ├── WorkflowTraceReplay.tsx  # Step-by-step replay
│           └── WorkflowStepInspector.tsx# Node I/O + LLM trace viewer
│
├── tests/
│   ├── test_agent.py                    # ✅ Workflow registry + memoization
│   ├── test_workflow_graph.py           # ✅ Layout + async edge classification
│   ├── test_workflow_trace.py           # ✅ Trace status, retries, LLM I/O
│   ├── test_research_article_graph.py   # ✅ Parallel tools + article generation
│   ├── test_content_generation_graph.py # ✅ Lesson/quiz/PBL + router fallback
│   ├── test_integration_clients.py      # ✅ Tavily + YouTube adapter unit tests
│   ├── test_llm.py                      # ✅ Groq router, fallback, cache
│   ├── interface/
│   │   └── test_local_ui_api.py         # ✅ Local workflow UI API + live key tests
│   ├── infrastructure/
│   │   └── test_infrastructure_stubs.py # Adapter guard contracts
│   └── test_cache.py                    # ✅ Cache-aside + wiring smoke tests
│
└── src/
    └── mcp_server/
        │
        ├── main.py                      # ✅ MCP entrypoint — bootstrap, settings, server.run()
        ├── local_ui_main.py             # ✅ Local workflow UI entrypoint (loopback only)
        ├── settings.py                  # ✅ Typed config (Groq, Tavily, YouTube, Supabase, cache)
        ├── operational_config.py        # ✅ Pydantic loader for repo-root config.json
        ├── wiring.py                    # ✅ Composition root — ports, workflows, cache, lazy builders
        │
        ├── domain/                      # Pure contracts — no LangChain / MCP / SDKs
        │   ├── interfaces.py            # ✅ IDataRepository, ISearchClient, IVideoSearchClient
        │   │                            # 📋 ISqlReadExecutor, IEmbeddingProvider, IVectorRetriever, IReranker
        │   ├── schemas.py               # ✅ DocumentHit, VideoResult
        │   │                            # 📋 ChunkHit, TextChunk, SqlQueryProposal, SqlQueryResult
        │   ├── query_policies.py        # 📋 SQL allowlists, table/column caps, SELECT-only rules
        │   ├── cache.py                 # ✅ ICacheStore port
        │   ├── cache_keys.py            # ✅ Deterministic cache key builders
        │   └── exceptions.py            # ✅ Domain errors → interface mapping
        │
        ├── application/                 # Agents, graphs, LangChain tools, orchestration
        │   ├── agent.py                 # ✅ Document-video graph + list_registered_workflows()
        │   ├── integration_runtime.py   # ✅ Lazy ISearchClient / IVideoSearchClient accessors
        │   ├── retrieval_runtime.py     # ✅ Lazy IEmbeddingProvider / IVectorRetriever / IReranker accessors
        │   ├── workflow_trace.py        # ✅ Per-node execution trace collection
        │   ├── workflow_llm_trace.py    # ✅ LLM prompt/output capture per node
        │   ├── workflow_graph.py        # ✅ Graph introspection + UI layout (async edges)
        │   ├── workflow_config.py       # ✅ WorkflowExecutionConfig runtime view
        │   ├── llm_router.py            # ✅ Groq capped fallback + per-complexity debounce
        │   ├── routing_chat_model.py    # ✅ LangChain adapter over LLMRouter
        │   ├── llm_models.py            # ✅ Groq model registry from catalog
        │   ├── llm.py                   # ✅ create_chat_model(settings) → BaseChatModel
        │   ├── parameter_builders.py    # 📋 Rule + state + optional LLM param builders
        │   ├── langchain_tools.py       # 📋 @tool wrappers (web, youtube, documents, sql)
        │   │
        │   └── agents/                  # ✅ One package per LangGraph workflow
        │       ├── content_generation/  #     Lesson → quiz + PBL (validation retries)
        │       │   ├── state.py
        │       │   ├── nodes.py
        │       │   ├── prompts.py
        │       │   ├── llm_output.py
        │       │   └── graph.py
        │       ├── research_article/    #     Plan → parallel Tavily/YouTube → article
        │       │   ├── state.py
        │       │   ├── nodes.py
        │       │   ├── prompts.py
        │       │   └── graph.py
        │       ├── tavily_search/       #     Single-node Tavily integration test
        │       │   └── graph.py
        │       ├── youtube_search/      #     Single-node YouTube integration test
        │       │   └── graph.py
        │       └── rag_retrieval/       # ✅ Semantic RAG: embed → retrieve → [rerank?] → merge
        │           ├── state.py
        │           ├── nodes.py
        │           └── graph.py
        │
        ├── interface/                   # MCP protocol + local UI adapters
        │   ├── mcp_server.py            # ✅ FastMCP instance
        │   ├── custom_tools.py          # ✅ health_check, search_youtube, build_lesson_enrichment_query
        │   │                            # 📋 search_web, query_supabase_sql
        │   ├── validation.py            # ✅ All MCP + local UI request/response models
        │   └── local_ui/                # ✅ FastAPI adapter (dev-only workflow explorer)
        │       ├── api.py               #     GET /api/workflows, POST /api/workflows/{id}/run
        │       └── schemas.py
        │
        └── infrastructure/              # Provider adapters — only layer with external SDKs
            ├── supabase_client.py       # ✅ IDataRepository (stub body; guards live)
            ├── tavily_search_client.py  # ✅ ISearchClient — Tavily HTTP API
            ├── search_client.py         # ✅ ISearchClient — DuckDuckGo fallback (stub)
            ├── youtube_client.py        # ✅ IVideoSearchClient — YouTube Data API v3
            ├── supabase_sql_executor.py # 📋 ISqlReadExecutor — parameterized read-only SQL
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
| `application/agent.py` | Application | Workflow registry (`list_registered_workflows`) for local UI |
| `interface/custom_tools.py` | Interface | MCP tool surface — validate in, delegate out |
| `interface/validation.py` | Interface | All MCP request/response Pydantic models |
| `domain/query_policies.py` | Domain | SQL agent safety rules before execution |
| `infrastructure/supabase_sql_executor.py` | Infrastructure | Execute validated `SqlQueryProposal` only |
| `wiring.py` | Entrypoint | Wire ports → LangChain tools → graphs → MCP tool handlers |
| `ui/` + `interface/local_ui/` | Dev tooling | Visualize registered graphs locally (not production MCP) |

### Growth path: packaged agents ✅ (in progress)

The first graph lived inline in `application/agent.py`. New workflows now follow the packaged layout:

1. **Graph package** under `application/agents/<name>/` (`state.py`, `nodes.py`, `graph.py`, optional `prompts.py`).
2. **Registration** in `list_registered_workflows()` for local UI introspection.
3. **API route** in `interface/local_ui/api.py` with matching Pydantic DTOs in `validation.py`.
4. **Tests** under `tests/test_<name>_graph.py` and layout contracts in `tests/test_workflow_graph.py`.
5. **UI spine + edges** in `workflow_graph._WORKFLOW_SPINES` / `_WORKFLOW_EDGES` when LangGraph drawable edges are incomplete (e.g. `Send` fan-out).

**Next packaged agents (planned):** `sql_read/`, `web_enrich/`. MCP `search_web` should delegate through a LangChain tool once `langchain_tools.py` ships.

---

## Settings and secrets (agentic extensions)

Extend `Settings` in `settings.py` (RAG fields shipped in Phase A):

| Variable | Used by |
| :--- | :--- |
| `GROQ_API_KEY` | `application/llm.py` via `LLMRouter` |
| `LLM_TEMPERATURE`, `LLM_COMPLEXITY` | Chat sampling + default complexity tier; **model ids** come from `list_active_groq_models` (not `LLM_MODEL`) |
| `TAVILY_API_KEY` | `TavilySearchClient` via `build_search_client()` |
| `YOUTUBE_API_KEY` | `YouTubeDataApiClient` via `build_video_client()` |
| `CACHE_TTL_*`, `CACHE_KEY_PREFIX_*` | Cache-aside for LLM, YouTube, web search, MCP tools (**not** RAG chunks) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Repository + vector index (Phase A) |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `EMBEDDING_WARM_ON_BOOT`, `EMBEDDING_CACHE_DIR` | ONNX model file cache + boot warm (`IEmbeddingProvider`) — **not** Redis query vectors |
| `RETRIEVAL_MODE`, `RETRIEVE_LIMIT`, `RERANK_ENABLED`, `RERANKER_MODEL`, `RERANK_TOP_N` | RAG retrieval graph defaults |
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
| `application/agent.py` | ✅ | Document-video graph, `list_registered_workflows()` |
| `application/agents/` | ✅ | `content_generation`, `research_article`, `tavily_search`, `youtube_search` |
| `application/integration_runtime.py` | ✅ | Lazy Tavily/YouTube client accessors |
| `application/retrieval_runtime.py` | ✅ | Lazy RAG port accessors |
| `application/workflow_trace.py` | ✅ | UI execution trace collection |
| `application/workflow_llm_trace.py` | ✅ | Per-node LLM I/O for observability |
| `application/workflow_graph.py` | ✅ | UI layout, async/retry edge kinds |
| `application/llm_router.py` | ✅ | Groq capped fallback + per-complexity debounce |
| `application/langchain_tools.py` | 📋 | LangChain `@tool` wrappers |
| `interface/custom_tools.py` | ✅ | MCP: `health_check`, `search_youtube`, `build_lesson_enrichment_query` |
| `interface/validation.py` | ✅ | MCP DTOs + all local UI run/trace models |
| `interface/local_ui/` | ✅ | Workflow explorer API (5 UI workflows) |
| `infrastructure/tavily_search_client.py` | ✅ | Live Tavily integration |
| `infrastructure/youtube_client.py` | ✅ | Live YouTube Data API v3 |
| `infrastructure/search_client.py` | stub | DuckDuckGo fallback |
| `infrastructure/supabase_client.py` | stub | Structured document queries |
| `wiring.py` | ✅ | Composition root — ports, cache, lazy builders |
| `ui/` | ✅ | React workflow explorer with trace replay |
| `OBSERVABILITY.md` | ✅ | Trace/replay/debugging guide |

---

## Implementation order

When building agentic features, follow the layer order from `ARCHITECTURE.md`:

```text
domain (ports + policies + entities)
  → application (LangChain tools, parameter builders, graph nodes)
  → infrastructure (adapter implementations)
  → interface (MCP tools + validation schemas)
  → entrypoint (wiring + settings)
  → tests
```

Within application layer, prefer this sequence:

1. Structured Supabase path (validated request + repository implementation)
1.5. Semantic RAG path (domain ports → pgvector adapters → `rag_retrieval` graph) — see [INVESTIGATION1.md](changelog/2026-07-22/domain/INVESTIGATION1.md)
2. Web and YouTube LangChain tools (ports already defined)
3. Parameter builders and conditional graph edges
4. LLM factory and optional LLM-assisted parameter nodes
5. SQL agent path (policies + executor + MCP tool) — last, highest risk

---

## Summary

| Concern | Owner layer | Mechanism |
| :--- | :--- | :--- |
| LLM access | Application (`llm.py`, `llm_router.py`) | `RoutingChatModel` + Groq fallback; no keys in nodes |
| LLM observability | Application (`workflow_llm_trace.py`) | Prompts, raw output, model name per trace step |
| Conditional parameters | Application (graph edges + state) | Rules → state merge → optional LLM → Pydantic |
| Parallel async tools | Application (`agents/research_article/`) | LangGraph `Send` + `defer=True` merge node |
| Tool calling (external) | Interface (`custom_tools.py`) | MCP tools validate and delegate |
| Tool calling (internal) | Application (graph nodes) | Nodes call ports via `integration_runtime` |
| Web search (Tavily) | Infrastructure → `ISearchClient` | `TavilySearchClient`; wired at bootstrap |
| YouTube search | Infrastructure → `IVideoSearchClient` | `YouTubeDataApiClient`; wired at bootstrap |
| Supabase structured read | Infrastructure → `IDataRepository` | Stub adapter; guards live |
| Semantic RAG | Infrastructure → `IVectorRetriever` + `retrieval_runtime` | ✅ Phase A — pgvector + fastembed ONNX |
| Workflow UI | Interface + `ui/` | Graph viz, trace replay, run summary |
| Wiring | Entrypoint (`wiring.py`) | Single composition root for all dependencies |

This architecture keeps **reasoning** (LLM + LangGraph) in the application layer, **contracts** in the domain, **protocol exposure** in the interface, and **provider details** in infrastructure — consistent with [ARCHITECTURE.md](./ARCHITECTURE.md).
