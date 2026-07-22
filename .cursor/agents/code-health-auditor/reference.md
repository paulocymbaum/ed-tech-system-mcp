# Code Health Reference — Ed-Tech MCP Server

Canonical catalog of **dead code**, **duplication**, **redundancy**, and **AI-generated maintainability smells** for this Domain-Driven MCP server (Clean Architecture + LangGraph + Supabase + external APIs).

The **code-health-auditor** agent uses this file as its investigation rubric. Findings must cite **evidence** (file paths, symbols, import graphs, duplicate excerpts) — not generic lint advice.

---

## System profile (what makes this codebase accumulate debt)

```text
src/mcp_server/
  domain/          — ports, schemas, cache keys (must stay lean)
  application/     — workflows, LangGraph agent, orchestration
  interface/       — MCP tools, Pydantic validation, local UI
  infrastructure/  — Supabase, Redis, YouTube, DuckDuckGo adapters
  wiring.py        — composition root (single import graph entry)
```

**Common debt sources** in agent-assisted repos:

1. **Scaffold leftovers** — stubs, TODOs, and unused modules from incremental layer builds
2. **Layer drift** — logic duplicated across interface and application after quick fixes
3. **Adapter sprawl** — near-identical HTTP/cache wrappers per external API
4. **Over-abstraction** — factories and base classes with a single subclass
5. **Orphan tests** — tests for removed symbols or never-wired features
6. **Changelog–code mismatch** — planned files in `IMPLEMENTATION*.md` that were never deleted when scope changed

---

## Pattern ID prefix legend

| Prefix | Category |
| :--- | :--- |
| `dead-` | Dead / unreachable / unreferenced code |
| `dup-` | Duplicated logic or copy-paste |
| `red-` | Redundant layers, wrappers, or validation |
| `ai-` | AI code smells — verbose, defensive, or over-engineered patterns |

---

## Layer-specific catalog

### Entrypoint (`main.py`, `settings.py`, `wiring.py`, `operational_config.py`, `local_ui_main.py`)

| ID | Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- | :--- |
| **dead-entry-unused-builder** | Unused `build_*` or factory never called from `main` / `wiring` | Function defined but no references in import graph | Confusing composition root; false “supported” paths | `wiring.py`, `main.py` |
| **dead-entry-stale-config** | Settings fields or `config.json` keys with no readers | Field on `Settings` or key in JSON never referenced | Misleading env docs; dead operational knobs | `settings.py`, `operational_config.py`, `config.json` |
| **dup-entry-dual-bootstrap** | Same env/config load in `main.py` and `local_ui_main.py` | Repeated `load_dotenv`, settings parse, wiring calls | Drift when one entrypoint is updated | `main.py`, `local_ui_main.py` |
| **red-entry-pass-through** | Wiring function that only instantiates one class with no branching | `def build_x(): return X(settings)` with no indirection value | Noise in composition root | `wiring.py` |
| **ai-entry-defensive-init** | try/except around every import or build with swallowed errors | Broad `except Exception: pass` at startup | Hides misconfiguration; hard to debug | `main.py`, `wiring.py` |

**Investigation commands:**

```bash
rg "def build_|def create_" src/mcp_server/wiring.py src/mcp_server/main.py
rg "class Settings|BaseSettings" src/mcp_server/settings.py -A 200
rg "load_dotenv|get_settings|build_" src/mcp_server/
```

---

### Interface (`interface/`)

| ID | Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- | :--- |
| **dead-ifc-unused-tool** | MCP tool registered but not in agent tool list / never documented | `@mcp.tool` with zero call sites or removed from `langchain_tools` | Dead surface area; security/review burden | `custom_tools.py`, `mcp_server.py` |
| **dead-ifc-unused-schema** | Pydantic models only referenced in tests or nowhere | Model in `validation.py` with no `model_validate` callers | Schema drift; false API contract | `validation.py`, `local_ui/schemas.py` |
| **dup-ifc-tool-boilerplate** | Identical try/except + logging wrapper on every tool | Copy-pasted decorator bodies | Fix-once-fix-many burden | `custom_tools.py` |
| **dup-ifc-validation** | Same field rules in MCP schema and application DTO | Duplicate `Field(...)` constraints | Inconsistent validation over time | `validation.py`, `domain/schemas.py` |
| **red-ifc-fat-tool** | Business logic that belongs in application layer | SQL, agent calls, or port logic inside tool handler | Untestable duplication with workflows | `custom_tools.py` |
| **red-ifc-double-validate** | `model_validate` then workflow validates again | Two validation passes on same payload | Redundant CPU; diverging rules | `custom_tools.py`, `workflows.py` |
| **ai-ifc-generic-handler** | `except Exception as e: return {"error": str(e)}` on every tool | Hides domain exceptions; loses error typing | `custom_tools.py` |
| **ai-ifc-verbose-docstring** | Multi-paragraph docstrings restating parameter types | Docstring repeats Pydantic field descriptions | Noise; obscures real behavior | `custom_tools.py` |

**Investigation commands:**

```bash
rg "@mcp\.tool|@server\.tool|def .+\(.*\).*:" src/mcp_server/interface/
rg "class .+\(BaseModel\)" src/mcp_server/interface/
rg "model_validate|validate_python" src/mcp_server/
```

---

### Application (`application/`)

| ID | Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- | :--- |
| **dead-app-unused-workflow** | Workflow function never called from interface or agent | `async def run_*` with no importers | Dead orchestration path | `workflows.py`, `workflow_graph.py` |
| **dead-app-unused-node** | LangGraph node registered but unreachable | `add_node` for symbol not on any path from entry | Graph complexity without behavior | `agent.py`, `workflow_graph.py` |
| **dead-app-stub** | `raise NotImplementedError` or `pass` in non-test production path | Placeholder left after scaffold | Runtime failure or silent no-op | `application/**/*.py` |
| **dup-app-workflow-logic** | Same port call sequence in workflow and agent tool path | Identical Supabase + search sequence in two modules | Bug fixes applied in one place only | `workflows.py`, `agent.py` |
| **dup-app-llm-prompt** | Copy-pasted system/human prompt blocks | Same string literals in multiple functions | Prompt drift | `agent.py`, `parameter_builders.py` |
| **red-app-thin-wrapper** | Function that only forwards to another with same signature | `return await other_fn(*args, **kwargs)` | Indirection without policy | `workflows.py` |
| **red-app-state-bloat** | Duplicate document lists in graph state and return value | Same data in `state["docs"]` and tool result | Memory + serialization waste | `agent.py` |
| **ai-app-god-module** | Single file >300 lines mixing graph, prompts, and I/O | `agent.py` doing everything | Hard to review and deduplicate | `agent.py` |
| **ai-app-any-escape** | `Any` or untyped `dict` on hot orchestration paths | Lost contracts between nodes | Refactor regressions | `application/**/*.py` |

**Investigation commands:**

```bash
rg "NotImplementedError|#\s*TODO|pass\s*$" src/mcp_server/application/
rg "add_node|add_edge|StateGraph" src/mcp_server/application/
rg "async def run_|async def execute_" src/mcp_server/application/
```

---

### Domain (`domain/`)

| ID | Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- | :--- |
| **dead-dom-unused-port** | Protocol or ABC method never implemented or called | Method on `IDataRepository` with zero implementers/callers | False abstraction | `interfaces.py` |
| **dead-dom-unused-schema** | Entity or value object never constructed | Class in `schemas.py` with no imports | Domain model noise | `schemas.py` |
| **dead-dom-unused-exception** | Exception class never raised or caught | `class FooError` with no `raise FooError` | Misleading error taxonomy | `exceptions.py` |
| **dup-dom-parallel-types** | Two models representing same concept (`Document` vs `DocumentHit`) | Overlapping fields with conversion glue | Mapping boilerplate | `schemas.py` |
| **red-dom-validation-in-domain** | Pydantic validators encoding interface concerns | URL format checks that belong at boundary | Layer violation + duplication | `schemas.py` |
| **ai-dom-over-modeling** | Nested models for one-off dicts used once | 4-level Pydantic tree for single MCP response field | Maintenance cost | `schemas.py` |

**Investigation commands:**

```bash
rg "class .+\(Protocol\)|class .+\(ABC\)" src/mcp_server/domain/
rg "class .+Error\(" src/mcp_server/domain/exceptions.py
rg "class .+\(BaseModel\)" src/mcp_server/domain/schemas.py
```

---

### Infrastructure (`infrastructure/`)

| ID | Pattern | Signal in code | Why it hurts | Where to look |
| :--- | :--- | :--- | :--- | :--- |
| **dead-inf-unused-adapter** | Adapter module not wired in `wiring.py` | Client class never instantiated | Dead integration code | `infrastructure/*.py`, `wiring.py` |
| **dead-inf-commented-block** | Large commented-out implementation | Old Supabase/query logic left in place | Review noise; accidental uncomment | All adapters |
| **dup-inf-client-pattern** | Copy-paste HTTP client setup across YouTube/search/Supabase | Identical timeout/retry/header blocks | Inconsistent fixes | `*_client.py`, `external_apis.py` |
| **dup-inf-cache-wrap** | Same cache-aside try/get/set sequence per adapter | Repeated boilerplate in `cached_adapters.py` | Missing shared helper (or over-helper if one-liner) | `cached_adapters.py` |
| **red-inf-leaky-adapter** | Adapter returns raw dicts plus domain models | Double serialization paths | Caller confusion | `supabase_client.py` |
| **red-inf-pass-through-cache** | Cache wrapper that only delegates without key policy | No TTL/key semantics difference vs inner | Pointless layer | `cached_adapters.py` |
| **ai-inf-swallow-errors** | `except Exception: return []` on external API failures | Masks outages as empty results | `search_client.py`, `youtube_client.py` |
| **ai-inf-magic-strings** | Table names, column names, cache keys inline repeated | Same string in 5+ places | Schema drift | All adapters |

**Investigation commands:**

```bash
rg "^\s*#.*(def |class |await |return )" src/mcp_server/infrastructure/
rg "httpx\.|create_client|timeout=" src/mcp_server/infrastructure/
rg "except Exception" src/mcp_server/infrastructure/
```

---

## Cross-cutting categories

### Dead code (global signals)

| ID | Pattern | Investigation |
| :--- | :--- | :--- |
| **dead-import** | Unused imports (`ruff` F401 if enabled) | `uv run ruff check src/ --select F401` |
| **dead-module** | `.py` file never imported from `wiring.py` / entrypoints | Build import graph from `wiring.py`, `main.py` |
| **dead-symbol** | Function/class with zero references | `rg "def symbol_name|class SymbolName"` across repo |
| **dead-test** | Tests importing removed modules | `tests/` import errors or tests for deleted APIs |
| **dead-changelog** | Files listed in IMPLEMENTATION but absent or obsolete | Compare `changelog/**/IMPLEMENTATION*.md` to `src/` |
| **dead-reexport** | `__init__.py` exports unused names | `rg "__all__"` and importers |

**Import-graph procedure:**

1. Start at `main.py`, `local_ui_main.py`, `wiring.py`.
2. BFS imports through `src/mcp_server/`.
3. Files/symbols not reachable are **candidates** (confirm not loaded dynamically).

### Duplicated code

| ID | Pattern | Investigation |
| :--- | :--- | :--- |
| **dup-near-identical** | Same block ≥6 lines with ≤2 token changes | Manual diff; consider `diff` on ripgrep hits |
| **dup-symmetric-adapters** | Parallel methods `find_documents` / `find_videos` with same structure | `infrastructure/`, `cached_adapters.py` |
| **dup-error-messages** | Same user-facing string in multiple layers | `rg "raise .+Error\(|detail=" src/` |
| **dup-config-defaults** | Default limits/timeouts defined in settings and again in code | `settings.py` vs `workflows.py` / `agent.py` |

### Redundant code

| ID | Pattern | Investigation |
| :--- | :--- | :--- |
| **red-wrapper-chain** | A wraps B wraps C with no added policy | Trace constructor injection in `wiring.py` |
| **red-alias** | `Foo = Bar` or trivial subclass adding nothing | `rg "class .+\(.+\):\s*pass" src/` |
| **red-duplicate-boundary** | Validation at MCP + application + domain for same fields | Compare `validation.py`, `schemas.py`, tool handlers |
| **red-compat-shim** | Backwards-compat function for callers that no longer exist | `rg "deprecated|backward|compat|legacy" src/` |

### AI code smells (maintainability anti-patterns)

| ID | Pattern | Signal | Why it hurts |
| :--- | :--- | :--- | :--- |
| **ai-excessive-try** | try/except around every statement | Nested try blocks | Hides real failure modes |
| **ai-silent-fallback** | `except: return None` / `return []` | Empty fallback on any error | Production data loss |
| **ai-todo-ship** | `# TODO` / `FIXME` / `HACK` in production paths | Markers in non-test code | Incomplete features shipped |
| **ai-over-factory** | Factory/builder for single implementation | `create_*` used once | Unnecessary indirection |
| **ai-generic-naming** | `data`, `result`, `handler`, `process`, `utils` modules | Vague identifiers | Hard to navigate |
| **ai-utils-dumping** | `utils.py` / `helpers.py` growing without domain | Catch-all module | God-file antipattern |
| **ai-comment-narration** | Comments restating the next line | `# increment counter` on `i += 1` | Noise |
| **ai-defensive-getattr** | `getattr(x, "foo", None)` when type is known | Unnecessary dynamism | Hides typos |
| **ai-kwargs-soup** | `**kwargs` through many layers | Lost parameter contract | Breaks tooling and review |
| **ai-placeholder-copy** | "This function does X" docstrings with no semantics | No invariants or edge cases | False documentation |
| **ai-dual-implementation** | Old and new code paths both kept "just in case" | Feature flags always true | Permanent branches |
| **ai-test-theatre** | Tests asserting mocks only, not behavior | `assert mock.called` without outcome check | False confidence |

**Investigation commands:**

```bash
rg "TODO|FIXME|HACK|XXX" src/mcp_server/ --glob '!**/tests/**'
rg "except.*:\s*$" src/mcp_server/ -A 1
rg "return \[\]|return None|return \{\}" src/mcp_server/
rg "def (handle_|process_|do_)" src/mcp_server/
find src/mcp_server -name 'utils.py' -o -name 'helpers.py'
```

---

## Severity rubric (for CODE_HEALTH_AUDIT findings)

| Severity | Criteria | Examples |
| :--- | :--- | :--- |
| **Critical** | Dead code on hot path that confuses control flow; duplicate/conflicting validation causing wrong behavior; silent swallow hiding data loss | Two competing `find_documents` paths; `except: return []` on Supabase reads |
| **High** | Large dead modules; substantial duplication (≥20 lines) on common paths; redundant layer violating architecture | Unused adapter still wired; copy-pasted tool handlers |
| **Medium** | Moderate duplication; stale config/settings; AI smells increasing review burden | Duplicate prompts; TODO in agent node; utils dumping ground |
| **Low** | Minor redundancy; cosmetic AI narration; safe dead code in tests-only helpers | Unused import; over-long docstring; single-use trivial wrapper |

**Removal safety:** tag findings as **safe to delete** | **verify callers** | **needs product decision** before recommending deletion.

---

## Recommended investigation order

1. **Build import graph** from entrypoints → list unreachable modules (dead-code candidates).
2. **Run static checks** — `uv run ruff check src/ tests/` (unused imports, obvious issues).
3. **Scan interface ↔ application boundary** — fat tools, double validation, duplicate workflows.
4. **Compare infrastructure adapters** — copy-paste client and cache patterns.
5. **Review domain model usage** — unused ports, schemas, exceptions.
6. **AI smell pass** — TODOs, broad except, silent fallbacks, utils modules, `Any` usage.
7. **Cross-check changelog** — `IMPLEMENTATION*.md` files vs actual `src/` tree.
8. **Correlate tests** — orphaned tests, mock-only assertions, missing coverage for deleted code.

---

## Evidence standards

Every finding in `CODE_HEALTH_AUDIT{N}.md` must include:

- **Location** — file path and symbol (function/class/module)
- **Pattern ID** — from this doc (e.g. `dup-inf-client-pattern`, `ai-excessive-try`)
- **Category** — dead | duplicate | redundant | ai-smell
- **Evidence** — excerpt, import graph note, or duplicate block reference (second location for dupes)
- **Recommendation** — delete | consolidate | move layer | refactor (minimal change)
- **Removal risk** — safe to delete | verify callers | needs product decision
- **Effort** — `trivial` | `small` | `medium` | `large`

Do **not** recommend deleting code that is part of a documented public MCP contract without noting **breaking change**. Respect `ARCHITECTURE.md` layer boundaries when consolidating.

---

## Related canonical docs

| Doc | Use for |
| :--- | :--- |
| `ARCHITECTURE.md` | Layer boundaries; where logic should live after deduplication |
| `AGENTIC_ARCHITECTURE.md` | Which tools/workflows are intentional; avoid deleting wired agent paths |
| `ENVIRONMENT_SETUP.md` | `ruff`, `mypy`, `pytest` commands for dead-code verification |
| `changelog/**/IMPLEMENTATION*.md` | Planned vs delivered files; scaffold leftovers |
