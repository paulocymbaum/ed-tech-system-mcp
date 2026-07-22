# Cursor configuration reference

This document describes every file under `.cursor/` — the Cursor IDE configuration that governs how AI agents work on this repository. It complements the canonical docs at the repo root and the `changelog/` agent memory system.

## Overview

```text
.cursor/
├── agents/          # Subagent playbooks (specialized workflows)
├── rules/           # Context rules (loaded on demand or by glob)
└── skills/          # Step-by-step procedural guides
```

These three scopes work together:

| Scope | Purpose | When Cursor loads it |
| :--- | :--- | :--- |
| **agents** | Full multi-phase workflows delegated via the Task tool | When you or an orchestrator invokes a named subagent |
| **rules** | Persistent constraints and routing tables | On demand (`alwaysApply: false`) or by file glob |
| **skills** | Detailed how-to for a specific procedure | When the task matches the skill description |

Persistent work artifacts live in `changelog/` (not in `.cursor/`). Rules and agents define *how* to read and write those artifacts.

---

## Agents (`.cursor/agents/`)

Subagents are specialized agents invoked through Cursor's Task tool (`subagent_type`). Each file is a self-contained playbook with phases, templates, and quality gates.

### Pipeline overview

For full feature delivery, agents run in this order (orchestrated by `master`):

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  master — defines build brief, groups backlog items by scope, gates     │
│           each stage, updates backlog/BACKLOG.md after homologation     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
    ┌───────────────────────────▼───────────────────────────────────────┐
    │  1. incremental-layer-builder                                       │
    │     INVESTIGATION{N}.md → IMPLEMENTATION{N}.md → execute code       │
    └───────────────────────────┬───────────────────────────────────────┘
                                │
    ┌───────────────────────────▼───────────────────────────────────────┐
    │  2. changelog-code-reviewer                                         │
    │     review branch vs changelog → CODE_REVIEW{N}.md                  │
    └───────────────────────────┬───────────────────────────────────────┘
                                │
    ┌───────────────────────────▼───────────────────────────────────────┐
    │  3. incremental-layer-builder (remediation)                         │
    │     fix Critical/Warning findings from CODE_REVIEW{N}.md            │
    └───────────────────────────┬───────────────────────────────────────┘
                                │
    ┌───────────────────────────▼───────────────────────────────────────┐
    │  4. test-homologator                                                │
    │     TEST{N}.md → tests → HOMOLOGATION.md                            │
    └─────────────────────────────────────────────────────────────────────┘
```

For **maintainability and performance audits** (investigate only — no code changes unless requested):

```text
                    refactor-planner (parallel orchestration)
                              ↓
         ┌────────────────────┴────────────────────┐
         ↓                                         ↓
performance-auditor                    code-health-auditor
         ↓                                         ↓
PERFORMANCE_AUDIT{N}.md                  CODE_HEALTH_AUDIT{N}.md
         └────────────────────┬────────────────────┘
                              ↓ synthesize
              changelog/{DATE}/refactor/REFACTOR{N}.md
                              ↓ triage / implement
                     backlog/BACKLOG.md + backlog/RICE.md
                              ↓ batched execution
                            master
```

### `master.md`

| Field | Value |
| :--- | :--- |
| **Name** | `master` |
| **Role** | End-to-end build orchestrator |
| **Implements?** | No — delegates only |
| **Invoke when** | Any feature, refactor, or scaffold that should ship with review and homologation; or batched backlog execution |

**Stages:**

0. **Define build intent** — parse request, scan `changelog/`, group same-scope backlog items into a batch, write a build brief (date, layer, acceptance criteria).
1. **Build** — delegate to `incremental-layer-builder`.
2. **Review** — delegate to `changelog-code-reviewer` (review only, no fixes).
3. **Remediate** — delegate to `incremental-layer-builder` again with findings from `CODE_REVIEW{N}.md`.
4. **Homologate** — delegate to `test-homologator`.
5. **Backlog update** — mark completed `backlog/BACKLOG.md` items `done` with `done-YYYY-MM-DD` tag and refresh summary counts.

**Batching:** Group open backlog tasks by layer and scope (e.g. infrastructure trivial cleanup, entrypoint startup, observability, cache hardening). One changelog increment per batch; run batches sequentially through the full pipeline.

**Gates:** Each stage must complete (artifacts exist, status fields set, verification commands pass) before the next starts. Stages never run in parallel.

**Output:** A `MASTER pipeline report` with artifact paths, verification results, and open deferrals.

---

### `incremental-layer-builder.md`

| Field | Value |
| :--- | :--- |
| **Name** | `incremental-layer-builder` |
| **Role** | Investigate, plan, and implement one architectural increment |
| **Background** | `true` (runs asynchronously) |
| **Invoke when** | Feature, refactor, scaffold, or remediation after code review |

**Three phases (strict order):**

| Phase | Output | Purpose |
| :--- | :--- | :--- |
| 1 — Investigation | `changelog/{DATE}/{LAYER}/INVESTIGATION{N}.md` | Gap analysis, minimal increment, scope in/out |
| 2 — Implementation plan | `changelog/{DATE}/{LAYER}/IMPLEMENTATION{N}.md` | Ordered checklist with verification steps |
| 3 — Execute | Source code + checked checklist | Implement tasks top-to-bottom |

**Layer names:** `domain`, `application`, `interface`, `infrastructure`, `entrypoint`.

**Task order in checklists:** domain → application → infrastructure → interface → entrypoint → tests → ruff → mypy → pytest.

**Constraints enforced:**
- Domain: no MCP, LangChain, Supabase, or `os.environ`
- Application: depends on ports, not concrete adapters
- Interface: Pydantic validation before application/domain
- Infrastructure: implements ports; `Settings` via constructor
- Entrypoint: sole `load_dotenv()` caller

---

### `changelog-code-reviewer.md`

| Field | Value |
| :--- | :--- |
| **Name** | `changelog-code-reviewer` |
| **Role** | Review branch code against changelog plans and architecture |
| **Implements?** | No — reviews and documents only |
| **Invoke when** | After implementation, before merge |

**Four phases:**

| Phase | Activity |
| :--- | :--- |
| 1 — Documentation | Scan `changelog/`, read INVESTIGATION/IMPLEMENTATION pairs |
| 2 — Layers | Cross-check planned files vs actual code per layer |
| 3 — Git | `git diff` against base branch, run verification commands |
| 4 — Write review | `changelog/{DATE}/{LAYER}/CODE_REVIEW{N}.md` |

**Verdicts:** `approve` · `approve with nits` · `request changes` · `blocked`

**Finding tiers:** Critical (must fix) · Warnings (should fix) · Suggestions (consider)

---

### `test-homologator.md`

| Field | Value |
| :--- | :--- |
| **Name** | `test-homologator` |
| **Role** | Behavior-driven test inventory, implementation, and homologation |
| **Background** | `true` |
| **Invoke when** | After feature work, before merge, or when domain contract coverage is missing |

**Four phases:**

| Phase | Output | Purpose |
| :--- | :--- | :--- |
| 1 — TEST inventory | `changelog/{DATE}/tests/TEST{N}.md` | Catalog behaviors from schemas, ports, workflows |
| 2 — Plan | `changelog/{DATE}/tests/IMPLEMENTATION{N}.md` | Test file checklist |
| 3 — Write & run | `tests/*.py` | Implement cases, run pytest |
| 4 — Homologate | `changelog/{DATE}/tests/HOMOLOGATION.md` | Coverage matrix and verdict |

**Changelog layer:** Always `tests` (cross-cutting).

**Anti-bias rules:** Behavior over implementation · contracts over convenience · fakes over mocks · no external API calls in unit tests · no speculative tests.

**Verdicts:** `homologated` · `homologated with gaps` · `blocked`

---

### `code-health-auditor.md`

| Field | Value |
| :--- | :--- |
| **Name** | `code-health-auditor` |
| **Role** | Evidence-based maintainability audit (dead code, duplication, redundancy, AI smells) |
| **Background** | `true` |
| **Implements?** | No — investigates and documents only |
| **Invoke when** | After major features, before refactors, during cleanup sprints |

**Four phases:** Scope → investigate (per `reference.md` rubric) → verify with `ruff`/`mypy`/`pytest` → write `changelog/{DATE}/code-health/CODE_HEALTH_AUDIT{N}.md`.

**Output:** Findings with severity tiers (Critical · Warning · Suggestion) and source IDs for backlog triage.

---

### `performance-auditor.md`

| Field | Value |
| :--- | :--- |
| **Name** | `performance-auditor` |
| **Role** | Evidence-based performance audit (MCP, LangGraph, cache, external API paths) |
| **Background** | `true` |
| **Implements?** | No — investigates and documents only |
| **Invoke when** | After major features, before production hardening, when latency is a concern |

**Four phases:** Scope → investigate (per `reference.md` rubric) → verify → write `changelog/{DATE}/performance/PERFORMANCE_AUDIT{N}.md`.

**Output:** Bottleneck findings with source IDs for backlog triage.

---

### `refactor-planner.md`

| Field | Value |
| :--- | :--- |
| **Name** | `refactor-planner` |
| **Role** | Parallel audit orchestrator and refactor synthesis |
| **Implements?** | No — delegates audits, writes plan only |
| **Invoke when** | After major features, before cleanup sprints, when triaging audit findings into implementation-ready refactors |

**Stages:**

0. **Audit brief** — scope, changelog paths, reuse vs fresh audits.
1. **Parallel audits** — launch `performance-auditor` and `code-health-auditor` in the same message (two Task calls).
2. **Gate** — both audit files exist.
3. **Synthesize** — `changelog/{DATE}/refactor/REFACTOR{N}.md` with `REMOVE` / `CHANGE` / `CONSOLIDATE` / `WIRE` / `DEFER` actions per file and snippet.
4. **Report** — action counts and top priorities.

**Output:** Deduplicated refactor actions citing audit IDs (`P01`, `H03`, etc.) with before/after snippets and execution order.

**Handoff:** Pass `REFACTOR{N}.md` to `incremental-layer-builder` for implementation.

---

## Rules (`.cursor/rules/`)

Rules provide routing tables and constraints. All current rules use `alwaysApply: false` — agents load them explicitly when the task matches.

### `documentation-matrix.mdc`

| Field | Value |
| :--- | :--- |
| **Trigger** | Any task — read minimum doc set only |
| **Globs** | None (agent-requestable) |

**Purpose:** Routes agents to the right canonical doc for each task type.

| Task | Read |
| :--- | :--- |
| Code in a layer | `ARCHITECTURE.md` (+ `AGENTIC_ARCHITECTURE.md` if agents/tools/LLM) |
| Environment / CI | `ENVIRONMENT_SETUP.md` |
| Secrets / Doppler | `secrets-env-safety.mdc` → `doppler-env-setup` skill |
| New work | changelog INVESTIGATION → IMPLEMENTATION → code → CODE_REVIEW |
| Tests / merge gate | changelog TEST → tests → HOMOLOGATION |
| Maintainability audit | `code-health-auditor` → `CODE_HEALTH_AUDIT{N}.md` |
| Performance audit | `performance-auditor` → `PERFORMANCE_AUDIT{N}.md` |
| Refactor plan from audits | `refactor-planner` → `REFACTOR{N}.md` (runs both auditors in parallel) |
| Backlog triage | `backlog/BACKLOG.md` + `backlog/RICE.md` |
| Batched backlog execution | `master` (groups same-scope items) |

Also maps tasks to the correct subagent (see [Agent selection](#agent-selection-quick-reference)).

---

## Engineering backlog (`backlog/`)

The backlog is the triage layer between audits and batched delivery.

| File | Purpose |
| :--- | :--- |
| `backlog/BACKLOG.md` | RICE-ordered tasks with status (`open` · `in_progress` · `done` · `deferred` · `wont_do`), source audit IDs, and checklists |
| `backlog/RICE.md` | Scoring table linking audit findings to backlog task IDs |

**Workflow:**

1. Auditors write `CODE_HEALTH_AUDIT{N}.md` or `PERFORMANCE_AUDIT{N}.md`.
2. Findings are merged into `BACKLOG.md` tasks (one PR may cover multiple audit IDs).
3. `master` groups open tasks by layer/scope and runs each batch through the delivery pipeline.
4. After homologation, `master` sets task status to `done`, stamps `done-YYYY-MM-DD`, checks checklist items, and updates summary counts.

Individual builders and reviewers do **not** edit the backlog — that is `master`'s post-homologation step.

---

### `changelog-agent-memory.mdc`

| Field | Value |
| :--- | :--- |
| **Trigger** | Creating or continuing changelog files |
| **Globs** | None (agent-requestable) |

**Purpose:** Defines the `changelog/` folder as persistent agent memory.

**Layout:**

```text
changelog/
└── {YYYY-MM-DD}/
    ├── {layer}/                    # domain, application, interface, infrastructure, entrypoint
    │   ├── INVESTIGATION{N}.md
    │   ├── IMPLEMENTATION{N}.md
    │   └── CODE_REVIEW{N}.md
    ├── code-health/
    │   └── CODE_HEALTH_AUDIT{N}.md
    ├── performance/
    │   └── PERFORMANCE_AUDIT{N}.md
    └── tests/
        ├── TEST{N}.md
        ├── IMPLEMENTATION{N}.md
        └── HOMOLOGATION.md
```

**Key rules:**
- `{N}` is monotonic per layer folder (1, 2, 3…)
- `IMPLEMENTATION{N}` must pair with `INVESTIGATION{N}` in the same folder
- `CODE_REVIEW{N}` references the matching investigation/implementation pair
- Status values: INVESTIGATION (`draft`/`approved`), IMPLEMENTATION (`planned`/`in_progress`/`done`), CODE_REVIEW (`draft`/`final`)
- Never skip changelog for feature/refactor/scaffold work
- Never store decisions only in chat

---

### `secrets-env-safety.mdc`

| Field | Value |
| :--- | :--- |
| **Trigger** | `.env`, Doppler, secrets, `settings.py` env loading |
| **Globs** | `*.env`, `.env.*` |

**Purpose:** Prevents secrets from entering git or agent artifacts.

**Never commit:** `.env`, `.env.*`, `*.env`, `scripts/doppler/*.env`

**Setup scripts (use these, not bare `doppler setup`):**

| Script | Purpose |
| :--- | :--- |
| `scripts/doppler/setup-local.sh` | Link repo to `ed-harness-system` / `dev` |
| `scripts/doppler/bootstrap-from-env-example.sh` | Upload empty placeholders to all configs |

**Agent rules:**
1. Never stage or commit env files
2. Never paste secret values into chat, commits, or changelog
3. Direct users to the Doppler dashboard for real credentials
4. Never use `load_dotenv(override=True)` or read env outside `main.py`
5. `APP_ENV=ci` in CI; `development` locally

---

## Skills (`.cursor/skills/`)

Skills are procedural guides with checklists. Cursor loads them when the task matches the skill description.

### `doppler-env-setup/SKILL.md`

| Field | Value |
| :--- | :--- |
| **Name** | `doppler-env-setup` |
| **Invoke when** | Configuring secrets, Doppler setup, env bootstrap, GitHub Actions sync, `APP_ENV` |

**Doppler project:** `ed-harness-system`

| Config | `APP_ENV` | Use |
| :--- | :--- | :--- |
| `dev` | `development` | Local development |
| `github_ci` | `ci` | GitHub Actions (sync target) |
| `stg` | `staging` | Staging deploy |
| `prd` | `production` | Production deploy |

**Workflow checklist:**
1. `doppler login`
2. `./scripts/doppler/setup-local.sh`
3. `./scripts/doppler/bootstrap-from-env-example.sh` (first time)
4. Fill values in Doppler dashboard
5. Verify with `doppler run -- uv run mcp-server` and git safety hooks

**References:** `ENVIRONMENT_SETUP.md`, `scripts/doppler/`, `scripts/hooks/block-env-files.sh`

---

## Changelog memory system

The `changelog/` directory is the cross-cutting memory layer that all agents read and write. It is not inside `.cursor/` but is defined by `.cursor/rules/changelog-agent-memory.mdc` and agent playbooks.

### File roles

| File | Written by | Purpose |
| :--- | :--- | :--- |
| `INVESTIGATION{N}.md` | incremental-layer-builder | Gap analysis, scope, proposed files |
| `IMPLEMENTATION{N}.md` | incremental-layer-builder | Checklist, task order, completion |
| `CODE_REVIEW{N}.md` | changelog-code-reviewer | Branch review vs plans and architecture |
| `TEST{N}.md` | test-homologator | Behavior catalog with bias-free validation methods |
| `IMPLEMENTATION{N}.md` (in `tests/`) | test-homologator | Test implementation checklist |
| `HOMOLOGATION.md` | test-homologator | Test run evidence and verdict |
| `CODE_HEALTH_AUDIT{N}.md` | code-health-auditor | Maintainability findings for backlog triage |
| `PERFORMANCE_AUDIT{N}.md` | performance-auditor | Performance bottleneck findings for backlog triage |
| `REFACTOR{N}.md` | refactor-planner | Merged remove/change/wire actions from both audits |

### Pairing rules

```text
INVESTIGATION1.md  ←→  IMPLEMENTATION1.md  ←→  CODE_REVIEW1.md
TEST1.md           ←→  IMPLEMENTATION1.md (tests/)  ←→  HOMOLOGATION.md
```

Multi-layer work uses separate folders per layer on the same date:

```text
changelog/2026-07-21/domain/INVESTIGATION1.md
changelog/2026-07-21/infrastructure/INVESTIGATION3.md
changelog/2026-07-21/code-health/CODE_HEALTH_AUDIT1.md
changelog/2026-07-21/performance/PERFORMANCE_AUDIT1.md
changelog/2026-07-21/refactor/REFACTOR1.md
changelog/2026-07-21/tests/TEST12.md
```

---

## Agent selection quick reference

| Your task | Agent or resource |
| :--- | :--- |
| New feature, refactor, or scaffold | `incremental-layer-builder` |
| Post-implementation review | `changelog-code-reviewer` |
| Test inventory, pytest, homologation | `test-homologator` |
| Full build → review → test cycle | `master` |
| Batched backlog execution | `master` (group by scope, update `BACKLOG.md` after homologation) |
| Dead code, duplication, maintainability audit | `code-health-auditor` |
| Performance bottlenecks, latency audit | `performance-auditor` |
| Refactor plan (parallel audits → change/remove actions) | `refactor-planner` |
| Backlog tasks and priorities | `backlog/BACKLOG.md`, `backlog/RICE.md` |
| Which doc to read | `documentation-matrix` rule |
| Changelog file conventions | `changelog-agent-memory` rule |
| Secrets and env safety | `secrets-env-safety` rule + `doppler-env-setup` skill |

---

## How to invoke agents in Cursor

### Via chat (natural language)

Ask Cursor to run a named agent:

- *"Use incremental-layer-builder to add caching to the YouTube adapter"*
- *"Run changelog-code-reviewer on the current branch"*
- *"Use master to implement document search with full review and homologation"*
- *"Use master to batch the open infrastructure backlog items"*
- *"Run code-health-auditor on the infrastructure layer"*
- *"Run performance-auditor before production hardening"*
- *"Use refactor-planner to synthesize a refactor plan from audits"*
- *"Plan from existing audits only"* (refactor-planner skips parallel Stage 1)

### Via Task tool (programmatic)

Parent agents (including `master`) delegate with:

```text
subagent_type: "incremental-layer-builder"
subagent_type: "changelog-code-reviewer"
subagent_type: "test-homologator"
subagent_type: "master"
subagent_type: "code-health-auditor"
subagent_type: "performance-auditor"
subagent_type: "refactor-planner"
```

Task prompts must be self-contained — include build brief, changelog paths, increment `{N}`, and prior stage outputs. Subagents do not inherit chat history.

### Partial runs

| User says | Agent stops after |
| :--- | :--- |
| "investigate only" / "plan only" | Phase 1 or 2 of incremental-layer-builder |
| "inventory only" | Phase 1 of test-homologator |
| "review only, no file" | Phase 3 of changelog-code-reviewer (chat only) |
| "audits only" | refactor-planner stops after Stage 2 (no REFACTOR file) |
| "plan from existing audits" / "synthesize only" | refactor-planner skips Stage 1 parallel audits |
| "scope only" / "build only" | master stops at requested stage (warns pipeline incomplete) |

---

## Relationship to canonical docs

```text
┌──────────────────────────────────────────────────────────────┐
│  .cursor/                                                    │
│  agents · rules · skills  →  HOW agents work                 │
└──────────────────────────────┬───────────────────────────────┘
                               │ read / write
┌──────────────────────────────▼───────────────────────────────┐
│  changelog/  →  WHAT was decided and done (agent memory)     │
└──────────────────────────────┬───────────────────────────────┘
                               │ triage
┌──────────────────────────────▼───────────────────────────────┐
│  backlog/  →  PRIORITIZED work queue (BACKLOG.md, RICE.md) │
└──────────────────────────────┬───────────────────────────────┘
                               │ must align with
┌──────────────────────────────▼───────────────────────────────┐
│  ARCHITECTURE.md · AGENTIC_ARCHITECTURE.md · ENVIRONMENT_SETUP.md │
│  →  WHY and WHERE (canonical constraints)                    │
└──────────────────────────────────────────────────────────────┘
```

| Conflict | Resolution |
| :--- | :--- |
| Layer boundaries | `ARCHITECTURE.md` wins |
| Orchestration semantics | `AGENTIC_ARCHITECTURE.md` wins |
| Environment and secrets | `ENVIRONMENT_SETUP.md` + `secrets-env-safety` rule |

---

## File index

| Path | Type | Summary |
| :--- | :--- | :--- |
| `.cursor/agents/master.md` | Agent | Pipeline orchestrator + backlog batching |
| `.cursor/agents/incremental-layer-builder.md` | Agent | Investigate → plan → implement |
| `.cursor/agents/changelog-code-reviewer.md` | Agent | Review vs changelog and architecture |
| `.cursor/agents/test-homologator.md` | Agent | Test inventory → pytest → homologation |
| `.cursor/agents/code-health-auditor.md` | Agent | Maintainability audit → `CODE_HEALTH_AUDIT{N}.md` |
| `.cursor/agents/performance-auditor.md` | Agent | Performance audit → `PERFORMANCE_AUDIT{N}.md` |
| `.cursor/agents/refactor-planner.md` | Agent | Parallel audits → `REFACTOR{N}.md` synthesis |
| `backlog/BACKLOG.md` | Backlog | RICE-ranked tasks and status tracking |
| `backlog/RICE.md` | Backlog | Audit ID → backlog task scoring |
| `.cursor/rules/documentation-matrix.mdc` | Rule | Doc and agent routing table |
| `.cursor/rules/changelog-agent-memory.mdc` | Rule | Changelog layout and memory protocol |
| `.cursor/rules/secrets-env-safety.mdc` | Rule | Env file and Doppler safety (glob: `*.env`) |
| `.cursor/skills/doppler-env-setup/SKILL.md` | Skill | Doppler setup checklist |
