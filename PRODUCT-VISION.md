# Product Vision: Ed-Tech MCP Server

This document describes the **functional layers** of the ed-tech MCP server from a product perspective: what each layer does for users, how layers interact, and what is live versus planned.

For implementation rules and file layout, see [ARCHITECTURE.md](./ARCHITECTURE.md). For agent graphs, LLM wiring, and tool taxonomy, see [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md). For local debugging and trace replay, see [OBSERVABILITY.md](./OBSERVABILITY.md).

---

## North star

**External AI products never hold Supabase service-role keys, raw SQL, or provider-specific APIs.** They call **stable MCP tools** over Streamable HTTP. The server validates every request, enforces domain policies, rate limits outbound calls, and orchestrates retrieval and reasoning before data reaches an LLM host.

```text
┌─────────────────────┐     Streamable HTTP      ┌──────────────────────────────┐
│  AI client / agent  │ ───── POST /mcp ────────▶ │  ed-tech-system-mcp          │
│  (LLM host)         │ ◀─── JSON-RPC + SSE ──── │  FastMCP + LangGraph + Groq  │
└─────────────────────┘                          └──────────────┬───────────────┘
                                                                │
         ┌──────────────────────────────────────────────────────┼────────────────────────┐
         ▼                          ▼                          ▼                        ▼
   Supabase (documents,        Groq (LLM routing)        YouTube Data API          Tavily (web)
   pgvector chunks)                                                                  search
```

**Primary users**

| User | Need | Layer they touch |
| :--- | :--- | :--- |
| LMS / copilot integrator | Document + video answers without backend keys | MCP tools (`find_documents`, `run_workflow`) |
| Agent builder | Multi-step workflows with trace replay | MCP tools + workflow API / local UI |
| Content team | Lesson, quiz, and article generation | MCP tools (`content_generation`, `research_article`) |
| Platform engineer | Deploy, secrets, cache, observability | Entrypoint, context, cache, infrastructure |

---

## Functional layer stack

Layers are ordered from **outer** (what clients see) to **inner** (pure contracts). Cross-cutting layers (context, cache, observability) span the stack.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. Transport & protocol          MCP Streamable HTTP / stdio (FastMCP)     │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. Interface & validation          MCP tools, Pydantic I/O, error mapping  │
├─────────────────────────────────────────────────────────────────────────────┤
│  3. Application & orchestration   LangGraph agents, workflows, LLM router │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. Domain & contracts            Ports, entities, policies, exceptions   │
├─────────────────────────────────────────────────────────────────────────────┤
│  5. Infrastructure & adapters     Supabase, YouTube, Tavily, Redis, ONNX    │
├─────────────────────────────────────────────────────────────────────────────┤
│  6. Knowledge & retrieval         RAG, vector store, structured document read │
├─────────────────────────────────────────────────────────────────────────────┤
│  7. SQL & analytics (planned)     Read-only SQL agent with policy gate      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Context layer (composition root) wiring.py + runtime accessors             │
│  Cache layer                      Redis cache-aside + file/model caches     │
│  Observability layer              Traces, metrics, local workflow UI        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Transport & protocol

**Purpose:** Expose a stable, versioned protocol surface so any MCP-compatible host can discover tools and invoke them without custom SDKs.

| Concern | Implementation | Status |
| :--- | :--- | :--- |
| MCP server | `interface/mcp_server.py` (FastMCP) | ✅ Live |
| Production transport | Streamable HTTP (`MCP_STATELESS_HTTP`) on Render | ✅ Live |
| Local / CI transport | stdio or HTTP per `settings.mcp_transport` | ✅ Live |
| Health endpoint | `/health` for platform probes | ✅ Live |

**Product promise:** One URL (`/mcp`) and a small tool catalog — no direct Postgres, PostgREST, or Groq calls from client code.

---

## Layer 2 — Interface & validation

**Purpose:** Every tool call is validated before orchestration; every response is normalized before it leaves the server. Malformed or oversized payloads never reach agents or databases.

| Concern | Implementation | Status |
| :--- | :--- | :--- |
| MCP tool registration | `interface/custom_tools*.py` | ✅ Live |
| Request/response schemas | `interface/validation.py`, `validation_workflow.py` | ✅ Live |
| Domain → MCP errors | `interface/error_mapping.py` | ✅ Live |
| Tool latency logging | Per-tool `duration_ms` in `custom_tools.py` | ✅ Live |

**MCP tool catalog**

| Tool | Product capability | Status |
| :--- | :--- | :--- |
| `health_check` | Liveness | ✅ |
| `find_documents` | Semantic/hybrid document search + related videos | ✅ |
| `search_youtube` | Educational video discovery | ✅ |
| `run_workflow` | Full document + video LangGraph with trace | ✅ |
| `research_article` | Web + YouTube research → journalistic article | ✅ |
| `content_generation` | Lesson → quiz + PBL project | ✅ |
| `search_web` | Standalone web search tool | 📋 Planned |
| `rag_search` | Chunk-level RAG with scores | 📋 Planned |
| `query_supabase_sql` | Natural language → validated read-only SQL | 📋 Planned |

**Tool template (non-negotiable):**

```text
raw JSON-RPC args → Pydantic validate → application → Pydantic validate → return
```

**Anti-pattern avoided:** “Smart tools” that query Supabase or call Groq inside MCP decorators.

---

## Layer 3 — Application & orchestration

**Purpose:** Coordinate multi-step agent workflows: conditional routing, parallel I/O, LLM reasoning, and parameter building — without binding to MCP or Supabase SDKs.

| Concern | Implementation | Status |
| :--- | :--- | :--- |
| Document + video workflow | `application/workflows.py` (`DocumentVideoWorkflow`) | ✅ Live |
| LangGraph agents | `application/agents/*`, `application/agent.py` | ✅ Live |
| LLM access | `application/llm.py`, `llm_router.py` (Groq tiers + fallback) | ✅ Live |
| Workflow timeouts / retries | `application/workflow_config.py` + `config.json` | ✅ Live |
| Execution traces | `application/workflow_trace.py`, `workflow_llm_trace.py` | ✅ Live |
| LangChain tools (internal) | `application/langchain_tools.py` | 📋 Planned |

**Registered workflows (local UI / workflow API)**

| Workflow ID | Product outcome | Supabase |
| :--- | :--- | :--- |
| `rag-retrieval` | Embed → retrieve → optional rerank → merged context | ✅ Read (pgvector RPCs) |
| `rag-validation` | Index fixture + benchmark retrieval quality | ✅ Write + read |
| `research-article` | Parallel web + YouTube → article | Indirect |
| `content-generation` | Lesson, quiz, PBL drafts | None |
| `tavily-search` / `youtube-search` | Single-capability graphs | None |
| Document + video graph | Sequential discovery (also via `run_workflow`) | ✅ Read |

**Parameter building (three stages):**

1. Rule-based defaults (limits, language, safe search)
2. Context merge from graph state (e.g. document title → video query)
3. Optional LLM assist → **Pydantic only** before any port call

---

## Layer 4 — Domain & contracts

**Purpose:** Single source of truth for business rules, entities, and technology-agnostic ports. No framework imports.

| Artifact | Role |
| :--- | :--- |
| `domain/interfaces.py` | Ports: `IDataRepository`, `ISearchClient`, `IVideoSearchClient`, `IEmbeddingProvider`, `IVectorRetriever`, … |
| `domain/schemas.py` | `DocumentHit`, `VideoResult`, `ChunkHit`, filters |
| `domain/cache.py` | `ICacheStore`, cache operation types, deterministic key rules |
| `domain/exceptions.py` | `ResourceNotFoundError`, `DomainValidationError`, … |
| `domain/invariants.py` | Shared guards (non-empty query, positive limits, credentials) |
| `domain/query_policies.py` | SQL allowlists, SELECT-only rules | 📋 Planned |

**Two Supabase access modes (product distinction)**

| Mode | Port | When to use |
| :--- | :--- | :--- |
| **Structured retrieval** | `IDataRepository.find_documents` | Known query shape; filters; default for copilots |
| **SQL agent (read-only)** | `ISqlReadExecutor` *(planned)* | Open-ended analytics; always through policy validation |

Structured retrieval is the **default**. SQL agent is **opt-in** and **not yet shipped**.

---

## Layer 5 — Infrastructure & adapters

**Purpose:** Concrete integrations behind domain ports. Only this layer imports Supabase, Redis, YouTube, Tavily, Groq, and ONNX runtimes.

| Adapter | Capability | Status |
| :--- | :--- | :--- |
| `supabase_client.py` | Document retrieval via embedding + vector retriever | ✅ Live |
| `youtube_client.py` | YouTube Data API v3 | ✅ Live |
| `tavily_search_client.py` | Tavily web search | ✅ Live |
| `search_client.py` | DuckDuckGo fallback | Stub |
| `groq_adapter.py` | Groq chat completions | ✅ Live |
| `embeddings/fastembed_adapter.py` | Local ONNX embeddings | ✅ Live |
| `retrieval/supabase_vector_*.py` | pgvector RPC retriever / index writer | ✅ Live |
| `retrieval/chroma_vector_*.py` | Local Chroma fallback | ✅ Live (local dev) |
| `cached_adapters.py`, `cached_llm.py` | Cache-aside decorators | ✅ Live |
| `redis_cache_store.py` | Redis `ICacheStore` | ✅ Live |
| `supabase_sql_executor.py` | Validated read-only SQL | 📋 Planned |

**Outbound protection:** Shared per-minute rate limiter on external APIs (`RateLimited*` wrappers).

---

## Layer 6 — Knowledge & retrieval (RAG + vector store)

**Purpose:** Turn educational content into searchable knowledge: chunk, embed, index in a vector store, and retrieve with semantic or hybrid ranking for copilots and agents.

This is a **vertical capability** that spans domain ports, infrastructure adapters, application graphs, and Supabase backend schema — not a separate Clean Architecture ring, but a product layer integrators care about.

### Backend contract (Supabase)

| Asset | Role |
| :--- | :--- |
| `documents` | Canonical content (title, body, course, tags, language) |
| `document_chunks` | Chunked text + **384-dim** `embedding`, FTS `tsvector` |
| `match_chunks` RPC | Semantic (cosine) retrieval |
| `hybrid_search_chunks` RPC | FTS + semantic fusion (RRF) — default mode |

Migration: `supabase/migrations/20260722120000_document_chunks.sql`.

### Retrieval pipeline

```text
User query
    → embed query (FastEmbed ONNX, local)
    → vector retriever (Supabase pgvector or local Chroma)
    → optional rerank (cross-encoder, gated by RERANK_ENABLED)
    → merge_context → LLM or MCP response
```

| Setting | Default (local) | Production (Render) |
| :--- | :--- | :--- |
| `VECTOR_STORE_BACKEND` | `auto` → Chroma if `SUPABASE_VECTOR_ENABLED=false` | `supabase` |
| `RETRIEVAL_MODE` | `hybrid` | `hybrid` or `vector` |
| `EMBEDDING_DIMENSION` | `384` | Must match pgvector column |

**Local vs production vector store**

- **Local default:** Chroma (`SUPABASE_VECTOR_ENABLED=false`) so developers can run without applied migrations.
- **Production:** Supabase pgvector (`VECTOR_STORE_BACKEND=supabase` in `render.yaml`).

**Ingestion:** The MCP server **reads** indexed content; LMS/content pipelines must populate `documents` / `document_chunks` (or use `rag-validation` / index writer ports in dev).

### RAG exposure today

| Surface | Capability | Status |
| :--- | :--- | :--- |
| `find_documents` | Document hits from chunk retrieval + optional videos | ✅ MCP |
| `run_workflow` | Document + video LangGraph | ✅ MCP |
| `rag-retrieval` workflow | Full chunk pipeline with scores and merged context | ✅ Workflow API / local UI |
| `rag_search` MCP tool | Same pipeline on public MCP | 📋 Planned |

### RAG caching policy (intentional)

| What | MCP layer | Backend (Supabase) |
| :--- | :--- | :--- |
| ONNX **model weights** | ✅ `EMBEDDING_CACHE_DIR` (image bake on Render) | — |
| Query embedding vectors (Redis) | ❌ **Disabled** | — |
| Chunk / document hits (Redis) | ❌ **Disabled** | Fresh reads via RPCs |
| Index + vectors | — | ✅ Source of truth |

**Why Redis RAG cache is off at MCP:** Stale chunks after reindex or soft-delete would mislead copilots. Retrieval freshness belongs in **Supabase/pgvector**, not a second cache in the orchestration layer.

---

## Layer 7 — SQL & analytics (planned)

**Purpose:** Answer open-ended analytical questions over allowlisted tables with **read-only**, **parameterized** SQL — without giving LLM hosts direct database access.

**Planned flow:**

```text
MCP: query_supabase_sql(question)
  → LLM proposes SqlQueryProposal
  → domain query_policies validate (SELECT only, allowlist, row cap)
  → ISqlReadExecutor.execute(proposal)
  → normalized rows → MCP response
```

| Concern | Status |
| :--- | :--- |
| `ISqlReadExecutor` port | 📋 Not in code yet |
| `query_policies.py` | 📋 Planned |
| `supabase_sql_executor.py` | 📋 Planned |
| MCP tool `query_supabase_sql` | 📋 Planned |

**Why deferred:** Higher risk than structured RAG; ships after structured retrieval and policy layer are stable. Structured `find_documents` remains the default integrator path.

---

## Context layer (composition root & runtime)

**Purpose:** Wire dependencies once per process boot and expose them through lazy getters so Interface and Application never import Infrastructure directly.

Not a Clean Architecture ring — the **runtime registry** that connects all layers.

| Component | Role |
| :--- | :--- |
| `wiring.py` | Composition root: builds adapters, cache, workflows, LLM |
| `ApplicationContext` | Boot snapshot: shared `ICacheStore`, workflow config, tool cache |
| `initialize_application_runtime()` | Called from `main.py` and local UI lifespan |
| `*_runtime.py` modules | `get_chat_model()`, `get_search_client()`, `get_document_video_workflow()`, … |

**Bootstrap sequence:**

```text
load_settings() → load_operational_config()
  → create_cache_store()          # single ICacheStore per process
  → configure_lazy_*()            # settings + cache passed to all builders
  → set_mcp_tool_cache()
  → MCP server starts
```

**Anti-pattern avoided:** Passing FastMCP `Context` or `os.getenv()` into graph nodes — credentials and adapters flow through wiring only.

---

## Cache layer

**Purpose:** Reduce cost and latency for **repeatable, safe-to-stale** operations while keeping **retrieval freshness** on the backend.

### Redis cache-aside (`CACHE_ENABLED`)

Local and CI keep `CACHE_ENABLED=false`. Staging and production should set `CACHE_ENABLED=true` plus `REDIS_URL`. RAG retrieve/embed operations stay uncached in Redis regardless.

| Operation | Cached? | Default TTL |
| :--- | :--- | :--- |
| LLM completions | ✅ | 3600s |
| YouTube search | ✅ | 3600s |
| Web search (Tavily) | ✅ | 300s |
| MCP tool I/O envelope | ✅ | 60s |
| RAG: `find_documents`, embeddings, chunk retrieve | ❌ Always off | — |

**Mechanics:** `ICacheStore` port → `RedisCacheStore` or `NoOpCacheStore`; `run_cache_aside` with per-key singleflight; deterministic SHA-256 keys from canonical params.

**Graceful degradation:** If Redis is down, requests succeed without cache (miss → delegate).

### File / image caches (always on for RAG infra)

| Cache | Location | Purpose |
| :--- | :--- | :--- |
| Embedding ONNX weights | `EMBEDDING_CACHE_DIR` | Avoid cold-start model download |
| HuggingFace scratch | `HF_HOME`, `XDG_CACHE_HOME` | Writable paths on read-only containers |
| Groq model catalog | `GROQ_MODEL_CATALOG_CACHE_PATH` | Model list metadata |

---

## Observability layer

**Purpose:** Let engineers and agent builders **see** what happened inside a workflow — node order, latencies, cache hits, LLM prompts — without production MCP clients carrying trace payloads by default.

| Surface | Audience | Status |
| :--- | :--- | :--- |
| Per-tool latency logs | Platform / SRE | ✅ |
| Cache hit/miss metrics | Platform | ✅ (`cache_observability.py`) |
| Workflow trace + LLM I/O | Agent builders | ✅ (`workflow_trace`, local UI) |
| LangGraph workflow explorer | Developers | ✅ (`interface/local_ui/`, `ui/`) |
| Workflow API (`:8877`) | Integrators needing graphs not on MCP yet | ✅ Self-hosted |

See [OBSERVABILITY.md](./OBSERVABILITY.md) for replay and debugging workflows.

---

## Layer interactions (integrator view)

### Pattern A — Copilot with tools (simplest)

```text
User question → LLM host picks find_documents → MCP validates → RAG on Supabase → videos → LLM synthesizes
```

### Pattern B — Full agent trace

```text
run_workflow / research_article → LangGraph trace (llm_io, node timings) → critic or planner agent reads trace
```

### Pattern C — LMS UI + trusted BFF

```text
Browser → your API → MCP (server-side) → Supabase
         never expose SUPABASE_SERVICE_ROLE_KEY to the browser
```

---

## Maturity matrix

| Functional layer | MVP (today) | Next | Future |
| :--- | :--- | :--- | :--- |
| Transport & protocol | Streamable HTTP MCP | — | — |
| Interface & validation | 6 live MCP tools | `search_web`, `rag_search` | `query_supabase_sql` |
| Application | 6 LangGraph workflows | LangChain tool surface | SQL agent graph |
| Domain | Ports + RAG entities | `query_policies` | Extended tenancy policies |
| Infrastructure | Supabase pgvector, Groq, YouTube, Tavily | DuckDuckGo live | SQL executor |
| Knowledge & retrieval | `find_documents`, rag-retrieval UI | `rag_search` on MCP | Federated sources |
| SQL & analytics | — | Policy + executor | MCP tool |
| Context | Single cache store, lazy wiring | — | — |
| Cache | Redis for LLM/integration; no RAG Redis | — | External metrics backend |
| Observability | Local UI + traces | Hosted workflow API productization | — |

---

## Success metrics (product)

| Metric | Layer | Target |
| :--- | :--- | :--- |
| Tool p95 latency (`find_documents`) | Interface + RAG | Stable under indexed corpus |
| Cache hit rate (LLM / YouTube) | Cache | Meaningful cost reduction in staging/prd |
| Retrieval freshness | Knowledge | No stale chunk incidents from MCP Redis |
| Integrator time-to-first-tool | Transport + Interface | Minutes with Doppler + smoke script |
| Agent debug time | Observability | Trace explains every node without re-run |

---

## Related documentation

| Document | Use when |
| :--- | :--- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Layer boundaries, ports/adapters, anti-patterns |
| [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md) | Graph semantics, tool taxonomy, capability flows |
| [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md) | Env vars, cache, RAG settings, CI |
| [OBSERVABILITY.md](./OBSERVABILITY.md) | Workflow UI, trace replay |
| [.integration.md](./.integration.md) | Internal integrator guide (deployment URLs) |
| [RENDER.md](./RENDER.md) | Production deploy, embedding cache on Render |

---

## Document history

| Date | Change |
| :--- | :--- |
| 2026-08-10 | Initial product vision — functional layers aligned with composition root, cache policy, and RAG/SQL/vector boundaries |
