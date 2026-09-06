# Observability

This document describes how to **inspect and debug** LangGraph workflow execution. It complements [ARCHITECTURE.md](./ARCHITECTURE.md) (layer boundaries) and [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md) (agent orchestration).

> **Local workflow UI removed:** The React + FastAPI workflow explorer (`ui/`, `interface/local_ui/`, `workflow-api`, `local_ui_main`) was removed as part of the RAG cleanup. Traces are still captured programmatically in tests via `workflow_trace.py` and `workflow_llm_trace.py`; no interactive UI is shipped today.

---

## Surfaces

| Surface | Purpose | When to use |
| :--- | :--- | :--- |
| **Application logs** | Startup, port calls, cache hits, tool outcomes | Production-style request tracing (`LOG_LEVEL` in [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md)) |
| **pytest** | Deterministic graph + trace contracts | CI and regression tests |
| **MCP tool logs** | JSON-RPC duration and outcome per tool | MCP client debugging |

---

## Trace fields

`invoke_graph_with_trace()` records an ordered list of LangGraph `stream_mode="updates"` steps. Every step includes:

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
| `llm_io` | Prompts, raw LLM text, model name, complexity, and tiktoken-based token counts (LLM nodes only) |

### LLM-specific fields

For nodes that call Groq (`generate_lesson`, `generate_quiz`, `generate_pbl`, `agent_plan_research`, `write_article`):

- **`input_snapshot.llm_request`** — `model_name` (Groq model id that served the call) and `llm_complexity` (1=LOW, 2=MEDIUM, 3=HIGH)
- **`output_update.model_name`** — same model id, duplicated for quick scanning
- **`output_update.llm_complexity`** — complexity tier used for routing
- **`llm_io.model_name`** — canonical model field alongside prompts and raw output
- **`llm_io.input_tokens`**, **`llm_io.output_tokens`**, **`llm_io.total_tokens`** — tiktoken estimates (`cl100k_base` by default; model-name hints may select another encoding); counts are `0` until `initialize_application_runtime` wires the token counter
- **`llm_io.token_breakdown`** — per-field counts: `system_prompt_tokens`, `user_prompt_tokens`, `raw_output_tokens`

The model name reflects the **actual provider model** after `LLMRouter` fallback (e.g. `llama-3.3-70b-versatile`), not only the configured `LLM_MODEL` default.

---

## Using traces in tests

Trace assertions answer:

- Which node failed validation and why?
- How many times did `generate_lesson` retry before succeeding?
- Did the graph take a failure shortcut to `merge_results`?
- Which model served a fallback LLM call?

Example patterns live in `tests/test_workflow_trace.py` and the graph-specific test modules (`test_content_generation_graph.py`, `test_research_article_graph.py`).

---

## Implementation map

| Component | Path |
| :--- | :--- |
| Trace collection (`astream` + state snapshots) | `src/mcp_server/application/workflow_trace.py` |
| LLM prompt/output capture | `src/mcp_server/application/workflow_llm_trace.py` |
| Token counting port / adapter | `src/mcp_server/domain/token_counting.py`, `src/mcp_server/infrastructure/token_counting/tiktoken_counter.py` |
| Model name resolution | `src/mcp_server/application/llm_model_name.py` |
| Router fallback + `last_used_model_id` | `src/mcp_server/application/llm_router.py` |
| Graph layout + edge kinds | `src/mcp_server/application/workflow_graph.py` |
| API DTOs | `src/mcp_server/application/content_generation_dtos.py` (`WorkflowTraceStepView`) |

Trace collection uses LangGraph streaming — no separate observability backend is required for local debugging.
