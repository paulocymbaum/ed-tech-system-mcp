# ed-tech-system-mcp

Domain-Driven MCP (Model Context Protocol) server for ed-tech workflows. The server exposes validated MCP tools backed by LangGraph agents, Supabase document retrieval, web search, and YouTube video discovery — all organized with Clean Architecture and DDD.

![LangGraph Workflow Explorer — browse workflows, run traces, and inspect node I/O locally](docs/assets/workflow-ui-explorer.png)

## What this project does

External clients (Cursor, other MCP hosts) call **MCP tools** that validate input with Pydantic, delegate to **application workflows** and **LangGraph agents**, and reach external systems through **domain ports** implemented in the infrastructure layer.

### MCP tools

| Tool | Purpose |
| :--- | :--- |
| `health_check` | Liveness probe |
| `find_documents` | Document retrieval enriched with related videos (pruned response payloads) |
| `search_youtube` | YouTube video search for educational content |
| `run_workflow` | Full document + video discovery LangGraph workflow |

All tool handlers are wrapped with **MCP tool caching** (when enabled), **per-tool latency logging**, and **domain error mapping** at the protocol boundary.

### Integrations

| Capability | Integration |
| :--- | :--- |
| Document retrieval | Supabase (Postgres / pgvector) |
| Web search | DuckDuckGo (optional Tavily) — wiring deferred until HTTP adapters land |
| Video discovery | YouTube Data API v3 |
| Agent orchestration | LangChain / LangGraph |
| Caching | Redis (`CACHE_ENABLED=true` required in production) |
| Local workflow UI | FastAPI + React (dev tooling) |

> **Adapter status:** Infrastructure adapters are scaffolded with domain guards and exception taxonomy; full HTTP implementations (BL-022) are deferred. MCP tools exercise the workflow and port contracts through the composition root.

## Architecture

The codebase follows **Clean Architecture** with five layers under `src/mcp_server/`:

```text
entrypoint  →  interface  →  application  →  domain  ←  infrastructure
(main.py)      (MCP tools)   (agents)        (ports)     (adapters)
```

| Layer | Path | Responsibility |
| :--- | :--- | :--- |
| **domain** | `domain/` | Entities, ports, domain exceptions — no framework imports |
| **application** | `application/` | LangGraph workflows, agent orchestration |
| **interface** | `interface/` | MCP tools, Pydantic validation, protocol adapters |
| **infrastructure** | `infrastructure/` | Supabase, search, YouTube, Redis adapters |
| **entrypoint** | `main.py`, `settings.py`, `wiring.py` | Bootstrap, settings, dependency injection |

**Read next:** [ARCHITECTURE.md](./ARCHITECTURE.md) for layer rules, patterns, and anti-patterns. [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md) for LLM wiring, tool taxonomy, and agent flows. [OBSERVABILITY.md](./OBSERVABILITY.md) for the local LangGraph workflow UI, execution replay, and trace debugging.

## Quick start

### Prerequisites

- Python **3.12** (see `requires-python` in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/) — environment and dependency manager
- [Doppler CLI](https://docs.doppler.com/docs/cli) (recommended for secrets) or a local gitignored `.env`

### Install

```bash
uv python install 3.12
uv sync --all-groups
```

### Configure secrets

Secrets never enter git. Use Doppler (team) or a local `.env` (solo dev).

```bash
doppler login
./scripts/doppler/setup-local.sh
./scripts/doppler/bootstrap-from-env-example.sh   # first time only — uploads placeholders
# Fill real values in the Doppler dashboard → ed-harness-system
```

Required variables: `APP_ENV`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `YOUTUBE_API_KEY`.

Optional: `GROQ_API_KEY` (only when an LLM path is invoked — lazy-init at first use), `TAVILY_API_KEY`, `LOG_LEVEL` (applied at bootstrap via `configure_logging()`), `CACHE_ENABLED` + `REDIS_URL` (production).

See [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md) and [.cursor/skills/doppler-env-setup/SKILL.md](./.cursor/skills/doppler-env-setup/SKILL.md) for the full secrets workflow.

### Run the MCP server

```bash
# With Doppler
doppler run -- uv run mcp-server

# With local .env (APP_ENV=development)
uv run mcp-server
```

### Run the workflow UI (optional)

Local dev UI for inspecting workflow graphs, running test executions, and replaying traces:

```bash
./scripts/dev/run-workflow-ui.sh
```

API: `http://127.0.0.1:8877` (default) · React dev server: `http://127.0.0.1:4173`

| View | What it shows |
| :--- | :--- |
| **Workflow explorer** | Sidebar of registered LangGraph workflows with run forms |
| **Graph canvas** | Compiled nodes, forward/retry/failure edges, live replay highlighting |
| **Execution replay** | Step-by-step trace with validation errors and retry decisions |
| **Node I/O inspector** | Per-step state snapshots, LLM prompts, and raw model output |

**Graph visualization** — retry loops and parallel branches are rendered on the canvas:

| Content generation (validation retries) | Research article (parallel tool calls) |
| :---: | :---: |
| ![Content generation workflow graph with retry edges](docs/assets/workflow-graph-content-generation.png) | ![Research article workflow graph with parallel search nodes](docs/assets/workflow-graph-research-article.png) |

**Trace replay & debugging** — after a run, scrub through each node, inspect failures, and read LLM I/O:

![Workflow trace replay with run summary, graph highlighting, and node I/O inspector](docs/assets/workflow-trace-replay.png)

**Node I/O inspector** — per-step state snapshots, validation errors, and LLM prompts/raw output:

![Node I/O inspector showing input state, output update, and LLM prompts for a retry step](docs/assets/workflow-step-inspector.png)

See [OBSERVABILITY.md](./OBSERVABILITY.md) for graph replay, node I/O inspection, and trace API details.

To refresh README screenshots after UI changes:

```bash
./scripts/dev/run-workflow-ui.sh   # in one terminal
npx -p playwright node scripts/dev/capture-ui-screenshots.mjs   # in another
```

## Development

### Day-to-day commands

```bash
uv sync --frozen              # after pulling lockfile changes
uv run mcp-server             # start server
uv run ruff check src/        # lint
uv run ruff format --check src/
uv run mypy src/              # type check
uv run pytest                 # tests (143 cases as of 2026-07-21)
```

### Engineering backlog

Audit findings are triaged into [`backlog/BACKLOG.md`](./backlog/BACKLOG.md) (RICE-ranked, traceable to changelog audits). As of 2026-07-21: **23 done**, **6 deferred** (adapter HTTP implementation, profiling, trace IDs). The `master` agent executes same-scope items in batches and updates backlog status after homologation.

### Add dependencies

```bash
uv add some-package           # runtime
uv add --group dev some-tool  # dev only
```

Do not use `pip install` in this repo — it bypasses the lockfile.

### Quality gates (CI parity)

```bash
uv sync --frozen --all-groups
uv run ruff check src/
uv run mypy src/
npm run lint:architecture   # layer imports + boundary patterns (also runs on git push)
uv run pytest
```

**Git hooks:** Husky **pre-commit** runs public-repo safety checks (sensitive files, tracked leaks, secret scanners); **pre-push** re-checks tracked safety then runs architecture lint — neither blocks the other tier.

Run quality-gate commands from the **repository root** (`ed-tech-system-mcp/`), not `ui/`. The same scripts are also available inside `ui/` via `npm run hooks:test` and `npm run lint:architecture`.

## Project layout

```text
.
├── src/mcp_server/          # Application source (layered)
├── tests/                   # pytest suites
├── ui/                      # React workflow graph UI
├── scripts/
│   ├── doppler/             # Secret bootstrap and local setup
│   ├── hooks/               # Husky pre-commit guards
│   └── dev/                 # Dev tooling (workflow UI launcher)
├── docs/
│   └── assets/              # README screenshots (workflow UI)
├── changelog/               # Agent long-term memory (investigations, reviews, tests)
├── backlog/                 # RICE-ranked engineering backlog (BACKLOG.md, RICE.md)
├── .cursor/                 # Cursor agents, rules, and skills — see CURSOR.md
├── ARCHITECTURE.md          # Layer boundaries and patterns
├── AGENTIC_ARCHITECTURE.md  # Agent graphs and tool orchestration
├── OBSERVABILITY.md         # Workflow UI, trace replay, debugging
├── ENVIRONMENT_SETUP.md     # uv, secrets, CI, MCP client config
└── CURSOR.md                # Cursor IDE configuration reference
```

## Documentation index

See the [full documentation matrix](#documentation-matrix) at the end of this file for canonical docs, changelog artifacts, Cursor rules/skills, and agent routing.

## Cursor / MCP client integration

Register the server in your MCP host using the project interpreter:

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "command": "doppler",
      "args": ["run", "--", "uv", "--directory", "/absolute/path/to/ed-tech-system-mcp", "run", "mcp-server"]
    }
  }
}
```

Alternative patterns (local `.env`, `uv` launcher) are in [ENVIRONMENT_SETUP.md § Cursor / MCP client integration](./ENVIRONMENT_SETUP.md#cursor--mcp-client-integration).

## Agent-driven development

This repo uses Cursor subagents, a `changelog/` memory system, and a `backlog/` task queue for feature work.

**Delivery pipeline** (orchestrated by `master`):

```text
incremental-layer-builder → changelog-code-reviewer → remediation → test-homologator → backlog update
```

**Audit pipeline** (feeds the backlog):

```text
code-health-auditor / performance-auditor → backlog/BACKLOG.md (RICE-ranked) → master (batched execution)
```

See [CURSOR.md](./CURSOR.md) for agent roles, rules, batching conventions, and invocation guidance.

## Documentation matrix

Read the **minimum** doc set for your task. Do not load everything.

### Canonical docs (repo root)

| Document | Read when |
| :--- | :--- |
| [README.md](./README.md) | First visit — overview, quick start, MCP tools, workflow UI |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Any code change — layers, ports/adapters, deps per layer, file layout, anti-patterns |
| [AGENTIC_ARCHITECTURE.md](./AGENTIC_ARCHITECTURE.md) | LangGraph/LangChain agents, LLM wiring, tool taxonomy, DB/web/video flows |
| [OBSERVABILITY.md](./OBSERVABILITY.md) | Local workflow UI, execution replay, trace/API debugging |
| [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md) | `uv`, lockfile, deps, env vars, `ruff`/`mypy`/`pytest`, CI, MCP client setup |
| [CURSOR.md](./CURSOR.md) | Cursor agents, rules, skills, and changelog workflow |

**Conflict resolution:** `ARCHITECTURE.md` wins on layer boundaries; `AGENTIC_ARCHITECTURE.md` wins on orchestration semantics.

### Engineering backlog

| Document | Read when |
| :--- | :--- |
| [backlog/BACKLOG.md](./backlog/BACKLOG.md) | RICE-ranked tasks from audits; status tracking for agent batches |
| [backlog/RICE.md](./backlog/RICE.md) | Scoring rubric and priority formula for backlog items |

### Changelog memory (`changelog/{DATE}/{LAYER}/`)

Agent long-term memory for investigations, implementations, reviews, audits, and test homologation.

| File pattern | Read | Write |
| :--- | :--- | :--- |
| `INVESTIGATION{N}.md` | Before coding — gaps, scope, minimal increment | Start of feature/refactor/scaffold work |
| `IMPLEMENTATION{N}.md` | During execution — checklist, status | After investigation; update while coding |
| `CODE_REVIEW{N}.md` | Before merge — review findings | After implementation (`changelog-code-reviewer`) |
| `TEST{N}.md` | Before writing tests — behavior catalog | Start of test/homologation work (`tests/` layer) |
| `HOMOLOGATION.md` | Verify coverage verdict | After tests pass (`test-homologator`) |
| `PERFORMANCE_AUDIT{N}.md` | Before perf work — bottleneck findings | Performance audit (`performance-auditor`) |
| `CODE_HEALTH_AUDIT{N}.md` | Before refactors/cleanup — dead/dup/redundant findings | Code health audit (`code-health-auditor`) |
| `REFACTOR{N}.md` | Before cleanup implementation — merged actions from audits | Refactor planning (`refactor-planner`) |

**Pairing:** `IMPLEMENTATION{N}` ↔ `INVESTIGATION{N}`; `CODE_REVIEW{N}` ↔ same `{N}`. `REFACTOR{N}` references matching `PERFORMANCE_AUDIT*` and `CODE_HEALTH_AUDIT*` from the same date slug. Folder layout and status values: [`.cursor/rules/changelog-agent-memory.mdc`](./.cursor/rules/changelog-agent-memory.mdc).

### Cursor rules & skills

| File | Read when |
| :--- | :--- |
| [`.cursor/rules/documentation-matrix.mdc`](./.cursor/rules/documentation-matrix.mdc) | Routing which doc to read or write for a task |
| [`.cursor/rules/changelog-agent-memory.mdc`](./.cursor/rules/changelog-agent-memory.mdc) | Creating or continuing changelog files |
| [`.cursor/rules/secrets-env-safety.mdc`](./.cursor/rules/secrets-env-safety.mdc) | `.env`, Doppler, secrets, `settings.py` env loading |
| [`.cursor/skills/doppler-env-setup/SKILL.md`](./.cursor/skills/doppler-env-setup/SKILL.md) | First-time or broken Doppler / local secret bootstrap |

### Cursor agents (`.cursor/agents/`)

| Agent | Invoke when |
| :--- | :--- |
| `incremental-layer-builder` | Feature, refactor, or scaffold work |
| `changelog-code-reviewer` | Post-implementation review |
| `test-homologator` | Test inventory, pytest, homologation |
| `performance-auditor` | Performance bottleneck audit |
| `code-health-auditor` | Dead code, duplication, maintainability audit |
| `refactor-planner` | Audit synthesis → change/remove refactor plan |
| `master` | Full build → review → test cycle |

### Quick routing

```text
Code in a layer?        → ARCHITECTURE.md (+ AGENTIC_ARCHITECTURE.md if agents/tools/LLM)
Workflow UI / traces?   → OBSERVABILITY.md
Environment / CI?       → ENVIRONMENT_SETUP.md
Secrets / Doppler?      → secrets-env-safety.mdc → doppler-env-setup skill
New work?               → changelog INVESTIGATION → IMPLEMENTATION → code → CODE_REVIEW
Tests / merge gate?     → changelog TEST → tests → HOMOLOGATION
Audits / cleanup?       → PERFORMANCE_AUDIT / CODE_HEALTH_AUDIT → REFACTOR → backlog
Cursor config?          → CURSOR.md
```

## License

See repository metadata for license information.
