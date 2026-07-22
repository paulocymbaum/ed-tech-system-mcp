# Observability

This document describes how to **inspect, replay, and debug** LangGraph workflows in local development. It complements [ARCHITECTURE.md](./ARCHITECTURE.md) (layer boundaries) and [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md) (agent orchestration).

---

## Overview

| Surface | Purpose | When to use |
| :--- | :--- | :--- |
| **Workflow UI** (React + FastAPI) | Visual graph, step replay, node I/O, LLM prompts | Debugging graph routing, validation retries, prompt/output issues |
| **Workflow run API** | Machine-readable trace JSON | Scripts, integration tests, custom tooling |
| **Application logs** | Startup, port calls, cache hits | Production-style request tracing (see `LOG_LEVEL` in [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md)) |
| **pytest** | Deterministic graph + trace contracts | CI and regression tests |

The workflow UI is **local development only** (`APP_ENV=development` or `local`, loopback bind). It is not exposed in production MCP transport.

---

## Local Workflow UI

### Start the UI

```bash
./scripts/dev/run-workflow-ui.sh
```

| Service | Default URL |
| :--- | :--- |
| React dev server | http://127.0.0.1:4173 |
| FastAPI workflow API | http://127.0.0.1:8877 |

The script kills stale processes on port `8877`, starts the API (with hot reload on `src/`), and proxies `/api` from Vite to FastAPI.

**Secrets:** Running LLM workflows requires `GROQ_API_KEY` (via Doppler or `.env`). Graph browsing works without credentials; execution returns `503` when the chat model is not wired.

![Workflow explorer — sidebar, run form, and graph canvas](../docs/assets/workflow-ui-explorer.png)

### Registered workflows

| Workflow ID | Description |
| :--- | :--- |
| `tavily-search` | Simple Tavily web search with normalized snippets |
| `youtube-search` | YouTube video search for educational content |
| `research-article` | Parallel Tavily + YouTube research → merged context → article |
| `content-generation` | Lesson → quiz + PBL with Groq, validation retries, and model fallback |

Select a workflow in the sidebar to load its graph structure.

---

## Graph visualization

The canvas shows the **compiled LangGraph** structure:

- **Forward edges** — normal execution path (solid)
- **Retry edges** — validation failure loops back to a `generate_*` node (dashed amber, labeled `retry`)
- **Failure edges** — exhausted retries shortcut to `merge_results` (dashed red, labeled `give up`)

Generation nodes (`generate_lesson`, `generate_quiz`, `generate_pbl`) are laid out **above** validation nodes so retry arcs remain visible.

During replay, the active node is highlighted (blue = ok, amber = retry, red = failed). Repeated attempts show `(#2)`, `(#3)`, etc.

| Content generation (retry edges) | Research article (parallel tool calls) |
| :---: | :---: |
| ![Content generation workflow graph](../docs/assets/workflow-graph-content-generation.png) | ![Research article workflow graph](../docs/assets/workflow-graph-research-article.png) |

---

## Running workflows and capturing traces

1. Open a workflow in the sidebar.
2. Fill in the run form (e.g. **topic** + **grade level** for `content-generation`).
3. Click **Run and capture trace**.

Each run records a **trace**: an ordered list of LangGraph `stream_mode="updates"` steps. Every step includes:

| Field | Description |
| :--- | :--- |
| `step` | 1-based execution index |
| `node_id` | LangGraph node name |
| `status` | `ok`, `failed`, or `retry` |
| `attempt` | How many times this node has run in the current workflow execution |
| `validation_errors` | Pydantic / JSON parse errors (when `status=failed`) |
| `retry_counts` | Snapshot of `*_retry_count` state keys after validate nodes |
| `input_snapshot` | Graph state **before** the node update |
| `output_update` | Partial state written by the node |
| `llm_io` | Prompts, raw LLM text, model name, and complexity (LLM nodes only) |

### Model name in input and output

For nodes that call Groq (`generate_lesson`, `generate_quiz`, `generate_pbl`):

- **`input_snapshot.llm_request`** — `model_name` (Groq model id that served the call) and `llm_complexity` (1=LOW, 2=MEDIUM, 3=HIGH)
- **`output_update.model_name`** — same model id, duplicated for quick scanning
- **`output_update.llm_complexity`** — complexity tier used for routing
- **`llm_io.model_name`** — canonical model field alongside prompts and raw output

The model name reflects the **actual provider model** after `LLMRouter` fallback (e.g. `llama-3.3-70b-versatile`), not only the configured `LLM_MODEL` default.

---

## Execution replay (debugging)

Below the graph, the **Execution replay** panel replays the trace step-by-step:

| Control | Action |
| :--- | :--- |
| **Play / Pause** | Auto-advance every 700ms |
| **Prev / Next** | Single-step navigation |
| **Reset** | Return to step 0 |
| **Click a step** | Jump directly to that step |

Use replay to answer:

- Which node failed validation and why?
- How many times did `generate_lesson` retry before succeeding?
- Did the graph take a failure shortcut to `merge_results`?

The **Node I/O** panel (below replay) shows full JSON for the selected step:

- **Input state** — topic, grade level, prior artifacts, `llm_request` (model + complexity)
- **Output update** — parsed `lesson` / `quiz` / `pbl`, or `*_validation_errors`, plus `model_name`
- **LLM system / user prompts** and **raw output** — exactly what was sent to and returned from Groq

![Trace replay with run summary, step timeline, graph highlighting, and node I/O inspector](../docs/assets/workflow-trace-replay.png)

### Refresh screenshots

After UI changes, regenerate assets for the README and this doc:

```bash
./scripts/dev/run-workflow-ui.sh   # terminal 1
npx -p playwright node scripts/dev/capture-ui-screenshots.mjs   # terminal 2
```

---

## HTTP API

### List workflows

```bash
curl -s http://127.0.0.1:8877/api/workflows | jq '.[].id'
```

### Run with trace

**Content generation:**

```bash
curl -s -X POST http://127.0.0.1:8877/api/workflows/content-generation/run \
  -H 'Content-Type: application/json' \
  -d '{"topic":"fractions","grade_level":"6th grade"}' \
  | jq '{topic, generation_complete, trace: [.trace[] | {step, node_id, status, attempt, model: .llm_io.model_name}]}'
```

**Document + video discovery:**

```bash
curl -s -X POST http://127.0.0.1:8877/api/workflows/document-video-discovery/run \
  -H 'Content-Type: application/json' \
  -d '{"query":"algebra","document_limit":5,"video_limit":2}' \
  | jq '.trace | length'
```

### Health

```bash
curl -s http://127.0.0.1:8877/api/health
# {"status":"ok","mode":"local","workflow_count":2}
```

### Timeouts and errors

| HTTP status | Meaning |
| :--- | :--- |
| `503` | Workflow runtime not wired (missing Supabase secrets at boot, or chat model unavailable) |
| `504` | Workflow exceeded `workflow_timeout` from `config.json` |

---

## Implementation map

| Component | Path |
| :--- | :--- |
| Trace collection (`astream` + state snapshots) | `src/mcp_server/application/workflow_trace.py` |
| LLM prompt/output capture | `src/mcp_server/application/workflow_llm_trace.py` |
| Model name resolution | `src/mcp_server/application/llm_model_name.py` |
| Router fallback + `last_used_model_id` | `src/mcp_server/application/llm_router.py` |
| Graph layout + edge kinds | `src/mcp_server/application/workflow_graph.py` |
| API DTOs | `src/mcp_server/interface/validation.py` (`WorkflowTraceStepView`) |
| Local UI API | `src/mcp_server/interface/local_ui/api.py` |
| React UI | `ui/src/` (`WorkflowGraphView`, `WorkflowTraceReplay`, `WorkflowStepInspector`) |

Trace collection uses LangGraph streaming — no separate observability backend is required for local debugging.

---

## Testing trace behavior

```bash
uv run pytest tests/test_workflow_trace.py tests/test_workflow_graph.py -q
```

These tests verify retry recording, LLM I/O capture, model name propagation, and graph layout invariants.

---

## Related configuration

| Setting | File / env | Effect on observability |
| :--- | :--- | :--- |
| `workflow_timeout` | `config.json` | Max seconds for a traced run |
| `node_retries` | `config.json` | Validation retry budget (conditional edges) |
| `agent_node_timeout` | `config.json` | Per-node LangGraph timeout |
| `GROQ_API_KEY` | Doppler / `.env` | Required for live LLM traces |
| `LLM_MODEL` | Doppler / `.env` | Preferred model; router may fall back |
| `LLM_COMPLEXITY` | Doppler / `.env` | Default complexity when not overridden per node |
| `LOG_LEVEL` | Doppler / `.env` | Verbosity of application logs |

---

## Limitations (current increment)

- Traces are **in-memory per run** — not persisted across server restarts.
- The UI does not yet stream live execution; run completes, then replay begins.
- Only workflows registered in `list_registered_workflows()` appear in the UI.
- Document-video nodes do not emit `llm_io` (no LLM in that graph today).

For production observability (metrics, distributed traces, log correlation), extend the infrastructure layer with your platform's telemetry — the local UI is intentionally scoped to **developer debugging**.
