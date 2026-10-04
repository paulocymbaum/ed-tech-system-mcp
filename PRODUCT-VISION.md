# Product Vision: Ed-Tech MCP Server

This document describes the **functional layers** of the ed-tech MCP server from a product perspective: what each layer does for users, how layers interact, and what is live versus planned.

**Historical note (2026-09):** Document RAG (`find_documents`, `run_workflow`, Chroma/pgvector on MCP) moved to the backend embedding service + `mcp-find-documents`. Live tools: [`docs/MCP_TOOL_CATALOG.md`](docs/MCP_TOOL_CATALOG.md).

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

**MCP tool catalog** (live — see `docs/MCP_TOOL_CATALOG.md` for auth)

| Tool | Product capability | Status |
| :--- | :--- | :--- |
| `health_check` | Liveness | ✅ |
| `search_youtube` | Educational video discovery | ✅ |
| `search_web` | Tavily web snippets | ✅ |
| `build_lesson_enrichment_query` | 4–5 term enrichment query | ✅ |
| `research_article` | Web + YouTube research → article | ✅ |
| `content_generation` | Lesson → quiz + PBL project | ✅ |
| Authoring / review / tutor tools | See MCP_TOOL_CATALOG | ✅ |
| `find_documents` / `run_workflow` | Document RAG | ❌ Moved to backend |

**Anti-pattern avoided:** “Smart tools” that query Supabase or call Groq inside MCP decorators (enrichment LLM is moving to application services).

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
| LangChain tools (internal) | `application/langchain_tools.py` | Deferred — not current SoR |

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

## Frontend product vision — Praxis Code v2 UI/UX

**Source:** [`praxis-code-v2.zip`](./praxis-code-v2.zip) — "Praxis Code — Homeschool Learning Management", an AI Studio-generated React prototype (62 files, React 19 + Tailwind v4 + `lucide-react` + `motion`). It is the **v2 design reference** for the learner/teacher experience. Delivery roadmap: [`roadmap.md`](./roadmap.md).

### What the prototype proves (product findings)

| Finding | Evidence in prototype | Implication |
| :--- | :--- | :--- |
| **Dual-role homeschool LMS** | `RoleSelectView` (student ⇄ educator), `RoleSwitcher` in sidebar | One shell, role-scoped nav and dashboards; roles must come from `tenant_memberships`, not local state |
| **Student experience is streak/XP-driven** | `WeeklyStreakBanner` (gradient hero), XP/level in `IStudent`, "Medalhas & XP" | Gamification fields (streak, XP, level) have **no backend table yet** — planned (see roadmap BE-1) |
| **Lesson = dual-panel workbench** | `LessonDetailView`: left theory + audio narration + interactive visualizer; right tabs (coding / project / quiz) | Maps 1:1 to existing `curriculum.lessons` + quizzes + PBL projects; needs a lesson-workspace composition view |
| **Live coding is first-class** | `LiveCodeEditor` (Python/JS tabs, run, 3-test suite, AI feedback panel) | Backend already has `curriculum.test_boilerplates`, `project_test_cases`, `project_deliveries`; missing: run-result + AI-feedback surface (BE-3) |
| **AI grading queue with human approval** | `AiGradingQueue`: suggested score + AI summary, "Aprovar Todas IA", filter chips, computer-vision note for maker photos | Human-in-the-loop grading: AI proposes, teacher approves. Extends `learner.project_delivery_reviews` (BE-4) |
| **AI pedagogical assistant** | `AiPedagogicalAssistant`: learning alerts ("Theo hesita em ZeroDivisionError"), weekly highlights, "recomendar lição de apoio" | Insight generation belongs to MCP/backend agents (`ai_generation_jobs`); UI only renders recommendations |
| **Teacher lesson planner + generators** | `WeeklyLessonPlanner`, `CreateLessonModal`, `QuizGeneratorModal` ("geração alinhada à BNCC") | Content creation flows **through the MCP authoring pipeline** (AGENTS.md non-negotiable #3) — the FE modals become thin clients over `content_generation`/`ai_generation_jobs` |
| **Weekly plan & resources views** | `WeeklyPlanView` (grade horária), `ResourcesView` (videos + external links) | Needs `curriculum.weekly_plan_slots` (BE-2); resources reuse `lesson_web_links` + `lesson_videos` (BE-6) |

### Aesthetic direction (design tokens to adopt)

| Token group | v2 direction | Current FE state | Action |
| :--- | :--- | :--- | :--- |
| Canvas & surfaces | **Light-first**: `#f8fafc` page, white cards, `slate-200` borders | Dark-first glass (`--bg-0: #0b0d14`) | Adopt dual-theme; light default (decision D-1) |
| Primary accent | `blue-600` (`#2563eb`), active-nav `shadow-blue-600/30` | Indigo glass (`--accent-0: #818cf8`) | Restate accent tokens to blue family |
| Dark anchors | Sidebar `#090b10`, editor `#0d1117`, dark button `#0f172a` | Whole app dark | Dark anchors survive as sidebar/code-editor surfaces |
| CTA gradient | `from-purple-600 via-indigo-600 to-blue-600` (buttons) and `from-blue-700 via-indigo-700 to-blue-800` (hero banners) | — | Add `--gradient-cta` / `--gradient-hero` tokens |
| Radius | `rounded-xl` controls, `rounded-2xl` inner, `rounded-3xl` cards/modals | `radius.css` (small scale) | Extend radius scale |
| Elevation | `shadow-xs → xl`, hover `-translate-y-0.5` + `card-transition` (0.2s cubic-bezier) | Glass shadows | Add elevation scale + motion token |
| Typography | **Plus Jakarta Sans** (UI), **Fira Code** (code) | system stack | Self-host both, extend `typography.css` |
| Feedback colors | emerald=completed/score, amber=in-progress, slate=not-started, rose=danger | `--success-0`/`--danger-0` only | Add `warning` (amber) + status-badge semantic aliases |
| Motion | **Pure CSS** — 200ms `cubic-bezier(.4,0,.2,1)` default, hover lift `-2px`, press `scale(.98)`, `zoom-in-95` modals, `slide-in-from-bottom-5` toasts, `pulse/ping` live dots; declared `motion` dep never imported | ad-hoc transitions | Motion becomes tokens (`motion.css`) + utilities; no JS animation lib; `prefers-reduced-motion` collapse added on top (roadmap WS-7) |
| Enforcement | — | grep/count gates only (00, 14) | New mechanical sensors: no raw hex/arbitrary classes outside `design-system/`, barrel-only imports, visual regression on `gate:deliver` (roadmap WS-8) |

**Component inventory to extract:** 6 atoms (`Button`, `Badge`, `Avatar`, `Card`, `ProgressBar`, `TabPill`), 8 molecules (`MetricStatCard`, `RoleSwitcher`, `AudioNarratorPlayer`, `VideoCard`, `QuizOptionCard`, `ChecklistItem`, `TestResultItem`, `StudentProgressItem`), 16 organisms (sidebar, header, streak banner, activity list/kanban, live code editor, fraction pizza, grading queue, planner, AI assistant, video/create/quiz/workspace modals), 1 template (`AppLayout`), 7 views. Full mapping with item IDs in [`roadmap.md`](./roadmap.md). Pages **without** a v2 counterpart (catalog, content map, course/module experience, quiz session, project delivery) are restyled by **extrapolation** — nearest-analog mapping onto v2 components and tokens under the same WS-8 enforcement, with no page-invented patterns (roadmap WS-9). The roadmap's **WS-10 matrix is the complete screen census** (every live + planned screen mapped to an adoption item and a visual-regression baseline), and **WS-11 schedules the legacy course-experience deletion** (`course-legacy/`, `estrategiaLegacy`, `structure='legacy'` branch) after the v2 adoption completes — aligned with POKAYOKE-PLAN Wave 5.2, ending with `maxLegacyFiles` 5 → 0.

### Boundary corrections the prototype requires (non-negotiable)

1. **No client-side AI keys.** The prototype calls Gemini with `GEMINI_API_KEY` in the browser. In this system, AI features route through **backend edge functions / MCP tools** (`ai_generation_jobs`, `content_generation`) — the FE never holds provider keys (North star, §Layer 1).
2. **No on-disk content.** Prototype `mockData.ts` lessons/quizzes are throwaway fixtures. Production lesson/quiz data flows from `curriculum.*` RPCs; authoring goes through the MCP pipeline only.
3. **Stack deltas are not part of this effort.** Prototype is React 19 + Tailwind v4 + `motion` + `@google/genai`; the FE is React 18 + Tailwind 3 + Radix + Zustand. We port **design language and IA**, not dependency majors (decision D-3).
4. **Stack rules apply.** Components go through `design-system/` tokens (no raw hex in features), state via `application/stores`, route state in the URL, new routes registered in `documented-routes.mjs`; every stroke ends at `gate:fast`.

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
| 2026-10-03 | Added **Praxis Code v2 UI/UX** section from `praxis-code-v2.zip`: product findings, aesthetic direction, component inventory, boundary corrections; delivery roadmap extracted to `roadmap.md` (formerly `backlog.md`) — incl. animation language (WS-7), design enforcement (WS-8), extrapolation to unprototyped pages (WS-9), complete screen census (WS-10), and legacy deletion plan (WS-11) |
