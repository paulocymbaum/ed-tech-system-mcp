# Public MCP tool catalog

Agent-facing catalog for **ed-tech-system-mcp** (Streamable HTTP `/mcp`).  
Staging host: `https://ed-tech-system-mcp.onrender.com`  
LMS browsers must use backend Pattern C BFFs — never call MCP with secrets from the SPA.

**SoR companions:** backend `MCP_INTEGRATION.md` · `INTEGRATION/` · `API_ENDPOINTS.md`  
**Authoring playbook:** [`AUTHOR_PUBLISH_PLAYBOOK.md`](./AUTHOR_PUBLISH_PLAYBOOK.md)

---

## Auth classes

| Class | Meaning |
|-------|---------|
| **none** | No tenant/user token required |
| **tenant** | Pass `tenant_id` (and often course/module/lesson slugs) |
| **user** | Learner/manager access token used by BFF or MCP host (Pattern C) |
| **manager** | Tool arg `manager_jwt` must be a **manager+ user** access token — not the service role |

---

## Tool list

| Tool | Auth | Purpose |
|------|------|---------|
| `health_check` | none | Liveness |
| `find_documents` | tenant | RAG documents + optional videos; optional `course_id` (course slug) scopes pgvector filter |
| `search_youtube` | none | YouTube enrichment only |
| `run_workflow` | tenant | LangGraph workflow + trace |
| `research_article` | none / context | Web + YouTube + LLM article |
| `content_generation` | optional tenant | Lesson → quiz → PBL drafts; graph-scoped when `tenant_id` + `course_slug` set |
| `validate_lesson` | none | Gate lesson README + meta |
| `validate_quiz` | none | Gate quiz option slugs / `correctOptionId` |
| `validate_project` | none | Gate PBL README + tests |
| `search_graph_nodes` | tenant | Topic graph placement (EF9 / RPC) |
| `save_to_backend` | **manager** | Upsert lesson (+ quiz/project) via public RPCs |
| `author_lesson_pipeline` | **manager** + tenant | search → generate → validate → save → publish note |
| `generate_mock_test_structure` | none | EF2-shaped 3-section mock scaffold |
| `validate_mock_test` | none | Gate mock section contract |
| `collect_project_review_context` | tenant | README, starter, last N deliveries |
| `project_review` | tenant | Grade 0–100 + persist via EF7 (grader path) |
| `socratic_tutor` | tenant | Hints first; **never** writes grades |

---

## Choosing a tool

| Need | Tool |
|------|------|
| Lowest-latency RAG + videos | `find_documents` |
| Agent observability / step replay | `run_workflow` |
| Videos only | `search_youtube` |
| Graph-scoped lesson authoring E2E | `author_lesson_pipeline` |
| Draft-only generation | `content_generation` |
| Manual save after edits | `validate_*` then `save_to_backend` |
| Topic placement | `search_graph_nodes` |
| Project grade (product path) | Prefer LMS BFF `request-project-review` → `project_review` |
| Tutor turn (product path) | Prefer LMS BFF `request-socratic-tutor` → `socratic_tutor` |

---

## Transport notes

1. `initialize` then `tools/list` / `tools/call` over JSON-RPC on `/mcp`.
2. Accept header: `application/json, text/event-stream`.
3. Pattern C from LMS: `mcp-health`, `mcp-find-documents`, `mcp-search-youtube`, `mcp-run-workflow` on Supabase edge — server holds MCP URL.
4. Optional `course_id` on `find_documents` / BFF `mcp-find-documents`: course **slug** (matches `documents.course_id`). Ingest: `scripts/ingest/index_documents.py --course-id`. Ops: backend `INTEGRATION/MULTI_COURSE_OPS.md`.
5. Writes that touch curriculum assert manager membership via the **user** token in `manager_jwt`.

---

## Integrator smoke (HTTP, not MCP)

Sample catalog + quiz write script (no AI): PraxisWeb `scripts/integrator-smoke.sh` (E15 / 15.3).
