# Public MCP tool catalog

Agent-facing catalog for **ed-tech-system-mcp** (Streamable HTTP `/mcp`).  
Staging host: `https://ed-tech-system-mcp.onrender.com`  
LMS browsers must use backend Pattern C BFFs — never call MCP with secrets from the SPA.

**Hosted `/mcp` is not a public API.** The BFF sends `Authorization: Bearer $MCP_INBOUND_TOKEN` plus `X-EdHarness-Caller-Jwt` (the signed-in user). Direct browser or anonymous `tools/call` is rejected.

**SoR companions:** backend `MCP_INTEGRATION.md` · `INTEGRATION/` · `API_ENDPOINTS.md`  
**Authoring playbook:** [`AUTHOR_PUBLISH_PLAYBOOK.md`](./AUTHOR_PUBLISH_PLAYBOOK.md)

---

## Auth classes

| Class | Meaning |
|-------|---------|
| **none** | Health only (`/health` HTTP and `health_check` behind inbound token) |
| **inbound** | Shared `MCP_INBOUND_TOKEN` on HTTP `/mcp` (BFF or operator) |
| **caller JWT** | Header `X-EdHarness-Caller-Jwt` — verified Auth user; must match `user_id` / `manager_jwt`; must be a tenant member when `tenant_id` is present |
| **manager** | Tool arg `manager_jwt` must equal the caller JWT and be a **manager+ user** access token — not the service role |

---

## Tool list

| Tool | Auth | Purpose |
|------|------|---------|
| `health_check` | none | Liveness |
| `build_lesson_enrichment_query` | caller JWT | 4-5 term enrichment query from course/module/lesson titles |
| `search_youtube` | none | YouTube enrichment only |
| `search_web` | none | Web search snippets (Tavily) for enrichment |
| `research_article` | none / context | Web + YouTube + LLM article |
| `content_generation` | optional tenant | Lesson → quiz → PBL drafts; graph-scoped when `tenant_id` + `course_slug` set |
| `validate_lesson` | none | Gate lesson README + meta |
| `validate_quiz` | none | Gate quiz option slugs / `correctOptionId` |
| `validate_project` | none | Gate PBL README + tests |
| `validate_test_boilerplate` | none | Gate harness `{{LEARNER_CODE}}` + runner_kind |

**E16 lockstep:** catalog project blobs (`stack`, `runConfig`, `testBoilerplate.body`, `runDependencies`) must keep `{{LEARNER_CODE}}`. MCP `validate_test_boilerplate` + `save_to_backend` stay aligned with PraxisWeb `INTEGRATION/CURRICULUM.md` and backend `get-course-catalog`.
| `search_graph_nodes` | tenant | Topic graph placement (EF9 / RPC) |
| `save_to_backend` | **manager** | Upsert lesson (+ quiz/project) via public RPCs |
| `author_lesson_pipeline` | **manager** + tenant | search → generate → validate → save → publish note |
| `generate_course_scaffold` | **manager** + tenant | Structure-only course graph `{ nodes, edges }`. BFF persists the proposal. Does not apply the live graph. |
| `generate_mock_test_structure` | none | EF2-shaped 3-section mock scaffold |
| `validate_mock_test` | none | Gate mock section contract |
| `collect_project_review_context` | tenant | README, starter, last N deliveries |
| `project_review` | tenant | Grade 0–100 + persist via EF7 (grader path) |
| `socratic_tutor` | tenant | Hints first; **never** writes grades |

---

## Choosing a tool

| Need | Tool |
|------|------|
| 4-5 term enrichment query for LMS search | `build_lesson_enrichment_query` |
| Videos only | `search_youtube` |
| Web snippets only | `search_web` |
| Graph-scoped lesson authoring E2E | `author_lesson_pipeline` |
| Structure-only course outline | `generate_course_scaffold` |
| Draft-only generation | `content_generation` |
| Manual save after edits | `validate_*` then `save_to_backend` |
| Topic placement | `search_graph_nodes` |
| Project grade (product path) | Prefer LMS BFF `request-project-review` → `project_review` |
| Tutor turn (product path) | Prefer LMS BFF `request-socratic-tutor` → `socratic_tutor` |

---

## Transport notes

1. `initialize` then `tools/list` / `tools/call` over JSON-RPC on `/mcp`.
2. Accept header: `application/json, text/event-stream`.
3. Pattern C from LMS: `mcp-health`, `mcp-search-youtube`, `mcp-search-web` on Supabase edge — server holds MCP URL. Lesson enrichment web search is served by the backend `mcp-search-web` BFF (not an MCP tool called directly by the browser).
4. Ingestion: `services/embedding-service/index-documents` (backend) is no longer the default enrichment path; web search (`mcp-search-web`) is used for study aids. Ops: backend `INTEGRATION/MULTI_COURSE_OPS.md`.
5. Writes that touch curriculum assert manager membership via the **user** token in `manager_jwt`.

---

## Integrator smoke (HTTP, not MCP)

Sample catalog + quiz write script (no AI): PraxisWeb `scripts/integrator-smoke.sh` (E15 / 15.3).
