# RICE Prioritization Matrix

**Date:** 2026-07-21  
**Sources:** [CODE_HEALTH_AUDIT1.md](../changelog/2026-07-21/code-health/CODE_HEALTH_AUDIT1.md) · [PERFORMANCE_AUDIT1.md](../changelog/2026-07-21/performance/PERFORMANCE_AUDIT1.md)

## Scoring legend

| Dimension | Scale | Definition |
| :--- | :--- | :--- |
| **Reach** | 1–10 | Share of future production requests, hot paths, or developers affected |
| **Impact** | 1–3 | Magnitude of maintainability, latency, or reliability improvement (3 = high) |
| **Confidence** | 0.0–1.0 | Evidence strength from static analysis and audit traces |
| **Effort** | person-days | `trivial` = 0.25 · `small` = 0.5 · `medium` = 1.0 · `large` = 2.0 |
| **RICE** | — | `(Reach × Impact × Confidence) / Effort` |

**Audit prefix:** `H` = code-health dead · `D` = duplication · `R` = redundancy · `A` = AI smell · `P` = performance · `O` = observability · `PC` = performance critical (future)

---

## Full matrix (sorted by RICE score)

| Rank | ID | Source | Category | Summary | Reach | Impact | Conf. | Effort (d) | RICE | Backlog |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | P03 | perf | cache default | Document and enforce `CACHE_ENABLED=true` + Redis for production | 8 | 2 | 0.90 | 0.25 | **57.6** | [BL-012 · done-2026-07-21](BACKLOG.md#bl-012) |
| 2 | P01 | perf | sequential I/O | Parallelize independent port calls in `DocumentVideoWorkflow` | 9 | 3 | 0.85 | 0.5 | **45.9** | [BL-010 · done-2026-07-21](BACKLOG.md#bl-010) |
| 3 | H05 | health | dead symbol | Wire or remove `ainvoke_with_workflow_timeout` | 6 | 2 | 0.90 | 0.25 | **43.2** | [BL-011 · done-2026-07-21](BACKLOG.md#bl-011) |
| 4 | P04 | perf | retry amplification | Wire `ainvoke_with_workflow_timeout`; tune retry policy for read-only nodes | 8 | 3 | 0.90 | 0.5 | **43.2** | [BL-011 · done-2026-07-21](BACKLOG.md#bl-011) |
| 5 | P14 | perf | timeout budget | Tune `agent_node_timeout` after adapter profiling | 6 | 2 | 0.80 | 0.25 | **38.4** | [BL-014](BACKLOG.md#bl-014) |
| 6 | P19 | perf | Groq timeout | Set explicit `timeout` on `ChatGroq` aligned with node budget | 5 | 2 | 0.80 | 0.25 | **32.0** | [BL-014](BACKLOG.md#bl-014) |
| 7 | H08 | health | unused schema | Implement `search_youtube` MCP tool with `VideoSearchRequest`/`Response` | 8 | 2 | 0.90 | 0.5 | **28.8** | [BL-006 · done-2026-07-21](BACKLOG.md#bl-006) |
| 8 | A04 | health | placeholder tools | Replace deferred `custom_tools.py` stub with real MCP tool registrations | 8 | 2 | 0.90 | 0.5 | **28.8** | [BL-006 · done-2026-07-21](BACKLOG.md#bl-006) |
| 9 | H04 | health | dead workflow | Integrate `DocumentVideoWorkflow` into LangGraph nodes | 10 | 3 | 0.95 | 1.0 | **28.5** | [BL-001 · done-2026-07-21](BACKLOG.md#bl-001) |
| 10 | D01 | health | dup orchestration | Consolidate workflow class and agent graph to single orchestration path | 10 | 3 | 0.95 | 1.0 | **28.5** | [BL-001 · done-2026-07-21](BACKLOG.md#bl-001) |
| 11 | A01 | health | dual implementation | Eliminate parallel skeleton graph vs real workflow paths | 10 | 3 | 0.95 | 1.0 | **28.5** | [BL-001 · done-2026-07-21](BACKLOG.md#bl-001) |
| 12 | R03 | health | duplicate Redis | Share single `ICacheStore` across composition-root factories | 7 | 2 | 0.95 | 0.5 | **26.6** | [BL-003 · done-2026-07-21](BACKLOG.md#bl-003) |
| 13 | P11 | perf | duplicate Redis | Same as R03 — one Redis connection at composition root | 7 | 2 | 0.95 | 0.5 | **26.6** | [BL-003 · done-2026-07-21](BACKLOG.md#bl-003) |
| 14 | P13 | perf | workflow timeout | Enforce `ainvoke_with_workflow_timeout` on graph invocations | 7 | 2 | 0.90 | 0.5 | **25.2** | [BL-011 · done-2026-07-21](BACKLOG.md#bl-011) |
| 15 | H02 | health | unwired builder | Wire `build_document_video_workflow` and `build_mcp_tool_cache` at entrypoint | 9 | 3 | 0.90 | 1.0 | **24.3** | [BL-002 · done-2026-07-21](BACKLOG.md#bl-002) |
| 16 | H09 | health | unwired cache | Wire `McpToolInteractionCache` into MCP tool handlers | 9 | 3 | 0.90 | 1.0 | **24.3** | [BL-002 · done-2026-07-21](BACKLOG.md#bl-002) |
| 17 | P02 | perf | missing tool cache | Wrap MCP tools with `get_or_invoke()` cache-aside | 9 | 3 | 0.90 | 1.0 | **24.3** | [BL-002 · done-2026-07-21](BACKLOG.md#bl-002) |
| 18 | P05 | perf | eager startup | Lazy-init `build_chat_model()` on first LLM/agent use | 7 | 2 | 0.85 | 0.5 | **23.8** | [BL-004](BACKLOG.md#bl-004) |
| 19 | P08 | perf | large payloads | Prune `DocumentHit` fields at MCP response boundary | 7 | 2 | 0.85 | 0.5 | **23.8** | [BL-013 · done-2026-07-21](BACKLOG.md#bl-013) |
| 20 | H06 | health | stale config | Bootstrap logging from `settings.log_level` in `main.py` | 6 | 2 | 0.90 | 0.5 | **21.6** | [BL-007](BACKLOG.md#bl-007) |
| 21 | H01 | health | unwired search | Wire `build_search_client()` into workflow or agent path | 6 | 2 | 0.80 | 0.5 | **19.2** | [BL-005](BACKLOG.md#bl-005) |
| 22 | O02 | obs | cache metrics | Log or export cache hit/miss rates | 6 | 2 | 0.80 | 0.5 | **19.2** | [BL-018 · done-2026-07-21](BACKLOG.md#bl-018) |
| 23 | O04 | obs | log level | Same as H06 — enable `LOG_LEVEL` for perf debugging | 5 | 2 | 0.90 | 0.5 | **18.0** | [BL-007](BACKLOG.md#bl-007) |
| 24 | O03 | obs | tool latency | Per-MCP-tool latency breakdown | 6 | 2 | 0.75 | 0.5 | **18.0** | [BL-019](BACKLOG.md#bl-019) |
| 25 | A05 | health | cache typing | Use Pydantic envelope for `McpToolInteractionCache` serialization | 5 | 2 | 0.85 | 0.5 | **17.0** | [BL-008 · done-2026-07-21](BACKLOG.md#bl-008) |
| 26 | P07 | perf | cache serialize | Prune/compress payloads before cache write | 5 | 2 | 0.75 | 0.5 | **15.0** | [BL-015](BACKLOG.md#bl-015) |
| 27 | O06 | obs | retry alerts | Alert on retry exhaustion and workflow timeout events | 5 | 2 | 0.70 | 0.5 | **14.0** | [BL-021](BACKLOG.md#bl-021) |
| 28 | P10 | perf | UI recompile | Memoize `list_registered_workflows()` / compiled graph for local UI | 3 | 1 | 0.95 | 0.25 | **11.4** | [BL-023](BACKLOG.md#bl-023) |
| 29 | A02 | health | Any escape | Type `ainvoke_with_workflow_timeout` with `DocumentVideoState` alias | 3 | 1 | 0.90 | 0.25 | **10.8** | [BL-011 · done-2026-07-21](BACKLOG.md#bl-011) |
| 30 | O01 | obs | port timing | Add structured timing spans on port calls | 7 | 2 | 0.75 | 1.0 | **10.5** | [BL-017](BACKLOG.md#bl-017) |
| 31 | P06 | perf | cache stampede | Add per-key singleflight lock on cache-aside miss | 6 | 2 | 0.80 | 1.0 | **9.6** | [BL-016](BACKLOG.md#bl-016) |
| 32 | P09 | perf | deep graph | Collapse graph nodes or delegate to `DocumentVideoWorkflow` as single node | 6 | 2 | 0.80 | 1.0 | **9.6** | [BL-001 · done-2026-07-21](BACKLOG.md#bl-001) |
| 33 | P12 | perf | sync LLM cache | Document async-only LLM contract or add sync cache path | 3 | 1 | 0.80 | 0.25 | **9.6** | [BL-024](BACKLOG.md#bl-024) |
| 34 | PC01 | perf | HTTP timeouts | Require `httpx` timeouts on all adapter HTTP clients at implementation | 9 | 3 | 0.70 | 2.0 | **9.45** | [BL-022](BACKLOG.md#bl-022) |
| 35 | H07 | health | unused exceptions | Raise domain exceptions from adapters/workflows | 5 | 1 | 0.85 | 0.5 | **8.5** | [BL-009](BACKLOG.md#bl-009) |
| 36 | A03 | health | adapter stubs | Implement adapter bodies; gate MCP tools until complete | 8 | 3 | 0.70 | 2.0 | **8.4** | [BL-022](BACKLOG.md#bl-022) |
| 37 | H03 | health | dead module | Delete or populate `external_apis.py` placeholder | 2 | 1 | 1.00 | 0.25 | **8.0** | [BL-025](BACKLOG.md#bl-025) |
| 38 | R04 | health | empty block | Remove empty `TYPE_CHECKING` block in `cache_config.py` | 2 | 1 | 1.00 | 0.25 | **8.0** | [BL-026](BACKLOG.md#bl-026) |
| 39 | D04 | health | config drift | Single source of truth for `config.json` defaults | 4 | 1 | 0.90 | 0.5 | **7.2** | [BL-027](BACKLOG.md#bl-027) |
| 40 | O05 | obs | trace IDs | Distributed trace IDs across workflow nodes | 4 | 2 | 0.60 | 1.0 | **4.8** | [BL-020](BACKLOG.md#bl-020) |
| 41 | D02 | health | symmetric stubs | Extract shared HTTP base when ≥2 adapters share timeout/retry | 3 | 1 | 0.70 | 0.5 | **4.2** | [BL-028](BACKLOG.md#bl-028) |
| 42 | D03 | health | cache wrap dup | Extract `_cache_aside()` helper if a fourth variant appears | 3 | 1 | 0.60 | 0.5 | **3.6** | — |
| 43 | R01 | health | thin wrapper | Keep `create_agent()` facade (accepted) | 1 | 1 | 1.00 | 0 | — | — |
| 44 | R02 | health | pass-through | Keep `create_mcp_server()` singleton (accepted) | 1 | 1 | 1.00 | 0 | — | — |
| 45 | P15 | perf | stdio transport | Accept stdio overhead at current scale (accepted) | 1 | 1 | 1.00 | 0 | — | — |
| 46 | P16 | perf | UI reload | Dev-only `reload=True` acceptable (accepted) | 1 | 1 | 1.00 | 0 | — | — |
| 47 | P17 | perf | cache keys | Stable cache keys — no action needed (positive) | 1 | 1 | 1.00 | 0 | — | — |
| 48 | P18 | perf | port limits | Bounded defaults — keep (positive) | 1 | 1 | 1.00 | 0 | — | — |

---

## Priority tiers

| Tier | RICE range | IDs | Theme |
| :--- | :--- | :--- | :--- |
| **P0 — Ship blockers** | ≥ 25 | BL-001 · done-2026-07-21, BL-002 · done-2026-07-21, BL-003 · done-2026-07-21, BL-010–BL-013 · done-2026-07-21 | Orchestration integration, composition wiring, core perf before MCP tools |
| **P1 — High value** | 15–24 | BL-004–BL-009, BL-011, BL-014–BL-019 | Startup, logging, adapters, timeouts, observability foundations |
| **P2 — Medium** | 8–14 | BL-016, BL-020–BL-022, BL-023–BL-027 | Stampede protection, tracing, adapter implementation, housekeeping |
| **P3 — Low / deferred** | < 8 | D03, R01, R02, P15–P18 | Accept or defer until scale demands |

---

## Cross-audit dependency map

```text
BL-001 (orchestration) ──┬── resolves H04, D01, A01, P09
BL-002 (wiring)        ──┬── resolves H02, H09, P02
BL-003 (shared cache)  ──┬── resolves R03, P11
BL-011 (timeouts)      ──┬── resolves H05, P04, P13, A02
BL-006 (MCP tools)       ──┬── resolves H08, A04
BL-022 (adapters)        ──┬── resolves A03, PC01
BL-007 (logging)         ──┬── resolves H06, O04
```

---

## Notes

- **Merged backlog items:** Multiple audit IDs often map to one PR (see [BACKLOG.md](BACKLOG.md)); RICE is scored per audit ID to preserve traceability.
- **Accepted items (R01, R02, P15–P18):** Intentionally excluded from backlog; documented as positive or architectural decisions.
- **D03:** Deferred until a fourth cache-aside variant appears; no backlog task assigned.
- Re-score after adapter implementation and production profiling (especially P14, P19, PC01).
