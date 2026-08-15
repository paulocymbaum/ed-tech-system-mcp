# Author publish playbook (E9)

Manager+ curriculum publishing for **agent-only authoring** — no in-app CMS in v1. Agents and integrators use MCP tools plus backend RPCs/edge functions with a **manager JWT** (or service role for CI import).

See also: PraxisWeb `INTEGRATION/CURRICULUM.md` (endpoint bodies and response shapes).

---

## Decision: agent-only (v1)

| Path | v1 | Notes |
|------|----|-------|
| Cursor / MCP agent | **Yes** | Primary author surface |
| Manager CLI / scripts | **Yes** | EF2 bundle import, direct RPC |
| In-app LMS author CMS | **No** | Deferred; E9.5 — no FE forms for upsert/publish |
| Browser BFF for save | **No** | E6.6 unchecked unless product adds author UI |

Authors use the **content map** in PraxisWeb for coverage (`exists` / `planned` / `orphan`) and copy MCP-oriented prompts; persistence always goes through backend APIs below.

---

## Auth

All write paths require **manager+** membership on the tenant (`manager`, `administrator`, `super_admin`).

```http
Authorization: Bearer <USER_JWT>
apikey: <SUPABASE_ANON_KEY>
```

MCP tools that persist (`save_to_backend`, EF2 import helpers) accept `manager_jwt` in the tool body — never embed service role in the SPA.

---

## Option A — Incremental upsert RPCs

Use when authoring one lesson (or quiz/project) at a time from an agent pipeline.

| Step | RPC / EF | Body highlights |
|------|----------|-----------------|
| 1. Resolve graph node | `search_graph_nodes` / MCP `search_graph_nodes` | `p_tenant_id`, `p_query`, `p_course_slug` → `node_id`, `graph_index` |
| 2. Upsert module (if new) | `POST /rest/v1/rpc/upsert_module` | `p_tenant_id`, `p_slug`, `p_course_id`, … |
| 3. Upsert lesson | `POST /rest/v1/rpc/upsert_lesson` | `p_module_id`, slug, title, `p_graph_node_id` |
| 4. Lesson README | `POST /rest/v1/rpc/upsert_lesson_content_document` | markdown + `source_path` |
| 5. Quiz tree | `POST /rest/v1/rpc/upsert_quiz_tree` | `p_lesson_id`, `p_quiz` |
| 6. Project tree | `POST /rest/v1/rpc/upsert_project_tree` | `p_lesson_id`, `p_project` |
| 7. Publish | `POST /rest/v1/rpc/publish_lesson` | `{ "p_lesson_id": "<uuid>" }` |

Catalog refresh is enqueued automatically after publish/upsert (EF3 queue).

**MCP coordination (E6):** `author_lesson_pipeline` → validate → `save_to_backend` wraps the RPC sequence above when implemented.

---

## Option B — EF2 bulk import

Use for full course or mock-module drops (migrations, seed, large refactors).

```http
POST /functions/v1/import-course-from-bundle
Authorization: Bearer <MANAGER_JWT>
Content-Type: application/json
```

Minimal bundle sketch:

```json
{
  "tenant_id": "<uuid>",
  "course": {
    "slug": "javascript",
    "title": "JavaScript",
    "graph_root_label": "JavaScript",
    "structure": "hierarchy"
  },
  "graph": { "nodes": [], "edges": [] },
  "modules": [],
  "lessons": [],
  "mock_tests": [],
  "quizzes": [],
  "projects": [],
  "content_documents": []
}
```

Processing order: graph → course → modules → lessons → **mock_tests** → quizzes → projects → content documents (≤500 rows per chunk).

Bulk publish after import:

```http
POST /functions/v1/bulk-publish-lessons
{ "lesson_ids": ["<uuid>"] }
```

---

## Mock test authoring (E9.2)

Replace legacy `create-mock-test` skill with MCP:

```text
generate_mock_test_structure(
  study_module_slug="01-javascript-fundamentals",
  duration_minutes=90,
  passing_score_percent=70,
)
```

Returns EF2-compatible `mock_tests[]` with three sections: **instructions → quiz → coding**.

Validate before import:

```text
validate_mock_test({ "module_slug": "...", "sections": [...] })
```

Then include the `mock_tests` array in an EF2 bundle (with matching mock module + section lessons).

---

## MCP tool reference (E9)

| Tool | Purpose |
|------|---------|
| `search_graph_nodes` | Thin wrapper over RPC `search_graph_nodes` / EF9 |
| `generate_mock_test_structure` | Build validated 3-section mock test payload |
| `validate_mock_test` | Shape check for EF2 `mock_tests[]` |
| `save_to_backend` | *(E6)* Persist lesson bundle with manager JWT |
| `author_lesson_pipeline` | *(E6)* Search → generate → validate → save |

Invoke via MCP Streamable HTTP (agent host) or local MCP server (`uv run python -m mcp_server.main`).

Example:

```json
{
  "tool": "search_graph_nodes",
  "arguments": {
    "tenant_id": "00000000-0000-4000-8000-000000000001",
    "query": "binary search",
    "course_slug": "javascript",
    "limit": 10
  }
}
```

---

## Verification

1. `GET /functions/v1/get-course-catalog?tenant_id=…&course_slug=…` — lesson appears with markdown.
2. PraxisWeb content map — leaf moves from **planned** → **exists** after publish + refresh.
3. Optional: `POST /functions/v1/bulk-publish-lessons` for batch publish after EF2 import.
