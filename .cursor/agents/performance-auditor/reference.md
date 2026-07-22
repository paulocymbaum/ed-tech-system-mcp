# Performance Bottleneck Reference — Ed-Tech MCP Server

Canonical catalog of performance risks, anti-patterns, and investigation signals for systems like this Domain-Driven MCP server (Clean Architecture + LangGraph + Supabase + external APIs).

The **performance-auditor** agent uses this file as its investigation rubric. Findings must cite **evidence** (file paths, code patterns, config values) — not generic advice.

---

## System profile (what makes this stack slow)

```text
MCP client (LLM host)
  → JSON-RPC / stdio transport
  → Interface validation (Pydantic)
  → Application workflow or LangGraph agent (LLM round-trips)
  → Domain ports
  → Infrastructure adapters (Supabase, DuckDuckGo, YouTube, Redis)
```

**Dominant latency sources** (typical order of impact):

1. **LLM inference** — agent nodes, SQL proposal, parameter enrichment
2. **Sequential external I/O** — Supabase + web + YouTube chained without parallelism
3. **Cold external API calls** — cache disabled or misconfigured TTL/prefixes
4. **Agent graph depth** — many nodes, retries, timeouts amplifying tail latency
5. **Payload size** — large document/video result sets serialized through MCP
6. **Transport overhead** — stdio framing, JSON encode/decode on every tool call

---

## Layer-specific bottleneck catalog

### Entrypoint (`main.py`, `settings.py`, `wiring.py`, `operational_config.py`)

| Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- |
| **Eager wiring of all adapters** | `build_*` called at import or startup regardless of tool used | Slow cold start; memory for unused clients | `wiring.py`, `main.py` |
| **Per-request composition** | New `SupabaseRepository` / Redis client per MCP tool call | Connection churn; no pool reuse | `wiring.py`, adapter `__init__` |
| **Sync bootstrap in async path** | `load_dotenv`, file I/O, config parse blocking event loop | Head-of-line blocking under concurrent tools | `main.py`, `operational_config.py` |
| **Timeout config not enforced** | `WorkflowExecutionConfig` set but graph nodes lack `timeout` / `retry` | Runaway agent loops; tail latency spikes | `config.json`, `agent.py`, `workflow_config.py` |
| **Global singletons with lazy init** | First tool call pays full wiring cost | P99 latency on first request | `custom_tools.py`, module-level state |

**Investigation commands / searches:**

```bash
rg "build_data_repository|build_search_client|build_video_client|create_cache_store" src/
rg "workflow_timeout|agent_node_timeout|node_retries" src/ config.json
```

---

### Interface (`interface/`)

| Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- |
| **Fat MCP tools** | Business logic, DB calls, or LLM prompts inside decorators | Extra work per call; untestable hot path | `custom_tools.py` |
| **Double validation** | Same Pydantic model validated twice (decorator + workflow) | CPU + allocation on every request | `validation.py`, `custom_tools.py` |
| **Large response payloads** | Returning full `DocumentHit` / raw rows without field pruning | MCP JSON-RPC bloat; host token pressure | `validation.py`, response schemas |
| **Missing MCP tool cache** | Identical tool args always hit downstream | Repeated Supabase/YouTube/web cost | `mcp_tool_cache.py`, tool wrappers |
| **Synchronous tool handlers** | `def tool(...)` wrapping async workflows with `asyncio.run()` | Thread/event-loop overhead; nested loops | `custom_tools.py` |

**Investigation searches:**

```bash
rg "@mcp\.tool|@server\.tool|def find_documents|def search_" src/mcp_server/interface/
rg "model_validate|validate_python" src/mcp_server/interface/
```

---

### Application (`application/`)

| Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- |
| **Sequential port calls** | `docs = repo.find(...); videos = video.search(...); web = search.search(...)` without `asyncio.gather` | Latency sums instead of max | `workflows.py` |
| **LLM in the critical path** | Every request invokes `create_chat_model` / agent node | Dominates wall-clock time | `agent.py`, `workflows.py` |
| **Unbounded agent loops** | Graph cycles without max iterations or tool-call caps | Token cost + timeout risk | `agent.py`, LangGraph edges |
| **Retry amplification** | `node_retries` from `config.json` on already-slow external calls | Multiplies worst-case latency | `agent.py`, operational config |
| **Redundant tool invocations** | Agent re-calls same LangChain tool with identical args | Duplicate I/O | `langchain_tools.py`, graph state |
| **Large state in graph** | Full document lists / SQL rows stored in `StateGraph` state | Memory + serialization between nodes | `agent.py`, state TypedDict |
| **Parameter builder LLM calls** | Stage 3 LLM enrichment when rules would suffice | Extra round-trip per tool | `parameter_builders.py` *(planned)* |

**Investigation searches:**

```bash
rg "await.*\n.*await" src/mcp_server/application/ --multiline
rg "StateGraph|add_node|add_edge|compile" src/mcp_server/application/
rg "retry|timeout|max_iterations" src/mcp_server/application/
```

---

### Domain (`domain/`)

| Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- |
| **Heavy validation on hot entities** | Complex `@field_validator` / nested models on every row | CPU per result in large lists | `schemas.py` |
| **Unbounded query contracts** | `limit` optional or very high default | Large DB reads; downstream slowness | `interfaces.py`, port signatures |
| **Cache key instability** | Keys include unordered dicts or timestamps | Cache never hits | `cache.py`, `build_cache_key` |
| **SQL policy too permissive** | High `max_rows` on `SqlQueryProposal` | Full table scans via agent path | `query_policies.py` *(planned)* |

Domain layer is usually **not** the top bottleneck — flag only when validation or policy allows unbounded work.

---

### Infrastructure (`infrastructure/`)

| Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- |
| **N+1 queries** | Loop over IDs calling Supabase per item | Linear DB round-trips | `supabase_client.py` |
| **Missing pagination** | `select("*")` without `limit` / `range` | Memory + network | `supabase_client.py` |
| **Sync client in async port** | `def find_documents` blocking inside `async def` | Blocks event loop | All adapters |
| **No connection pooling** | New HTTP client per request | TLS handshake overhead | `supabase_client.py`, `youtube_client.py` |
| **Cache-aside stampede** | No lock on cache miss; thundering herd on cold key | Duplicate external calls | `cached_adapters.py` |
| **JSON serialize on every cache op** | `model_dump()` + `json.dumps` for large lists | CPU on hot path | `cached_adapters.py` |
| **Redis round-trip per field** | Multiple `get`/`set` instead of pipeline | Latency multiplication | `redis_cache_store.py` |
| **External API quota** | YouTube `search.list` without batching or field masks | Quota exhaustion; throttling | `youtube_client.py` |
| **Web search latency** | DuckDuckGo synchronous scrape | Unpredictable P99 | `search_client.py` |
| **No timeout on HTTP** | `httpx`/`requests` without `timeout=` | Hung requests block workers | All HTTP adapters |

**Investigation searches:**

```bash
rg "for .+ in .+:\s*\n\s*await|for .+ in .+:\s*\n\s*self\._" src/mcp_server/infrastructure/ --multiline
rg "\.select\(|\.rpc\(|table\(" src/mcp_server/infrastructure/
rg "timeout|Client\(|create_client" src/mcp_server/infrastructure/
rg "await self\._cache\.(get|set)" src/mcp_server/infrastructure/
```

---

## Cross-cutting patterns

### Caching (`ICacheStore`, `cached_adapters.py`, `mcp_tool_cache.py`)

| Risk | Investigation |
| :--- | :--- |
| Cache disabled by default (`CACHE_ENABLED=false`) | `settings.py`, env docs |
| TTL too low for stable data | `cache_config.py`, `CACHE_TTL_*` env vars |
| Key prefix collisions across environments | `CACHE_KEY_PREFIX_*` |
| Stale reads after writes | No invalidation strategy documented |
| Large values in Redis | Serialized document/video lists exceed memory/network sweet spot |

### LangGraph / agent orchestration

| Risk | Investigation |
| :--- | :--- |
| Deep graphs (5+ nodes) for simple retrieval | `agent.py`, `workflow_graph.py` |
| LLM chooses tools sequentially | Graph design; no parallel tool node |
| `agent_node_timeout` < slowest port sum | `config.json` vs realistic I/O budget |
| Retries on non-idempotent operations | Retry policy on write paths (if any) |

### MCP transport

| Risk | Investigation |
| :--- | :--- |
| Stdio single-threaded processing | `main.py` transport mode |
| Logging full payloads at INFO | Log volume + I/O |
| No streaming for large results | Single JSON blob per response |

### Observability gaps (hard to optimize what you don't measure)

| Risk | Investigation |
| :--- | :--- |
| No timing spans on port calls | Missing structured logs / metrics |
| No cache hit-rate metrics | `cached_adapters.py` only returns hit/miss implicitly |
| No per-tool latency breakdown | Cannot prioritize fixes |

---

## Severity rubric (for PERFORMANCE_AUDIT findings)

| Severity | Criteria | Examples |
| :--- | :--- | :--- |
| **Critical** | Predictable production incidents: unbounded work, blocking event loop on hot path, missing timeouts on external I/O | No HTTP timeout; SQL agent without row cap; sync DB in async handler |
| **High** | Significant latency on common paths; fix likely >20% improvement | Sequential Supabase + YouTube + web; cache disabled in prod config; N+1 queries |
| **Medium** | Noticeable under load or at P99 | Double Pydantic validation; large MCP payloads; suboptimal TTL |
| **Low** | Micro-optimizations or future risk | Minor serialization cost; planned modules not yet implemented |

---

## Recommended investigation order

1. **Trace one hot path end-to-end** — e.g. `find_documents` or document+video workflow from `custom_tools.py` → `workflows.py` → ports → adapters.
2. **Check operational knobs** — `config.json` timeouts/retries; `CACHE_ENABLED` and TTL env vars in `settings.py`.
3. **Scan infrastructure adapters** — sync/async, loops, pagination, HTTP timeouts.
4. **Review application orchestration** — sequential vs parallel I/O; agent graph depth.
5. **Review interface boundary** — payload size, tool cache usage, validation duplication.
6. **Note observability gaps** — what cannot be measured today.

---

## Evidence standards

Every finding in `PERFORMANCE_AUDIT{N}.md` must include:

- **Location** — file path and symbol (function/class)
- **Pattern ID** — reference section from this doc (e.g. `infra-n-plus-one`, `app-sequential-io`)
- **Impact hypothesis** — which path and latency dimension (wall-clock, CPU, memory, quota)
- **Recommendation** — minimal fix aligned with `ARCHITECTURE.md` layer boundaries
- **Effort** — `trivial` | `small` | `medium` | `large`

Do **not** recommend violating Clean Architecture (e.g. caching inside domain, direct Supabase in MCP tools).

---

## Related canonical docs

| Doc | Use for |
| :--- | :--- |
| `ARCHITECTURE.md` | Layer boundaries; where fixes may land |
| `AGENTIC_ARCHITECTURE.md` | Agent flows, caching targets, wiring responsibilities |
| `ENVIRONMENT_SETUP.md` | Cache env vars, Redis optional group, pytest-asyncio |
| `config.json` | `node_retries`, `workflow_timeout`, `agent_node_timeout` |
