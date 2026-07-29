# Environment Setup

This guide defines the **safest, reproducible** way to build the Python environment for the Domain-Driven MCP server described in [ARCHITECTURE.md](./ARCHITECTURE.md).

The goals are:

- **Isolation** — dependencies never touch the system Python.
- **Reproducibility** — every machine installs the same resolved versions.
- **Least privilege** — production installs only runtime packages; secrets stay out of source control.
- **Auditability** — dependency changes are reviewable via lockfile diffs.

---

## Recommended toolchain

| Tool | Role | Why |
| :--- | :--- | :--- |
| **[uv](https://docs.astral.sh/uv/)** | Environment + dependency manager | Fast resolver, built-in venv, lockfile with hashes, single tool for the full workflow |
| **`pyproject.toml`** | Project metadata and dependency declarations | Standard PEP 621 format; aligns with Clean Architecture packaging under `src/` |
| **`uv.lock`** | Exact resolved dependency graph | Committed to git; prevents silent drift between dev, CI, and deployment |
| **`.venv/`** | Project-local virtual environment | Auto-created by `uv`; never committed |

> **Do not mix `pip install` and `uv` inside this project.** Installing packages with `pip` bypasses the lockfile and breaks reproducibility.

### Fallback (stdlib only)

If `uv` cannot be installed, use `python3 -m venv .venv` and `pip-tools` (`requirements.in` → `requirements.txt`). The `uv` workflow below is still the canonical approach for this repository.

---

## Python version policy

| Constraint | Value | Rationale |
| :--- | :--- | :--- |
| **Minimum** | Python **3.12** | Matches current ecosystem support for `mcp`, `fastmcp`, `langchain`, and `pydantic` v2 |
| **Recommended** | Python **3.12.x** (latest patch) | Use the same minor version locally, in CI, and in deployment |
| **Upper bound** | `<3.13` in `requires-python` | Avoids surprise breakage until the stack is explicitly tested on newer interpreters |

Pin the interpreter in `pyproject.toml`:

```toml
[project]
requires-python = ">=3.12,<3.13"
```

Install a managed interpreter with uv (preferred over relying on the OS Python):

```bash
uv python install 3.12
```

---

## Dependency groups

Dependencies are split to match the architectural layers in [ARCHITECTURE.md](./ARCHITECTURE.md) and to keep production surfaces small.

### Runtime (`[project.dependencies]`)

These map directly to the stack defined in the architecture:

| Package | Layer | Notes |
| :--- | :--- | :--- |
| `fastmcp` | Interface / Entrypoint | MCP server transport and tool routing. Pin to an **exact** version in the lockfile. |
| `langchain`, `langgraph` | Application | Agent orchestration and multi-step workflows |
| `pydantic>=2` | Domain / Interface | Strict validation at MCP boundaries |
| `supabase` | Infrastructure | Postgres / pgvector client |
| `duckduckgo-search` | Infrastructure | Default open-source web search adapter (swap for `tavily-python` if configured) |
| `google-api-python-client` | Infrastructure | YouTube Data API v3 adapter for searching educational videos linked to documents |
| `redis` | Infrastructure | Optional Redis cache for Supabase, YouTube, web search, and MCP tool I/O |
| `python-dotenv` | Entrypoint | Load gitignored `.env` in local dev only (`override=False`) |
| `pydantic-settings` | Entrypoint | Typed, validated `Settings` object; `SecretStr` for credentials |

> The official `mcp` SDK is pulled in transitively by `fastmcp`. Do not add a separate unconstrained `mcp` dependency unless you intentionally migrate off `fastmcp`.

### Development (`[dependency-groups] dev`)

Install only in local and CI dev workflows — **never** in production MCP runtime images:

| Package | Purpose |
| :--- | :--- |
| `pytest`, `pytest-asyncio` | Unit and integration tests per layer |
| `ruff` | Linting and formatting |
| `mypy` | Static type checking (especially Domain and Application ports) |
| `httpx` | HTTP mocking in Infrastructure tests |

---

## Initial project bootstrap

Run these commands from the repository root **once** when scaffolding the environment (before or alongside the `src/` layout from [ARCHITECTURE.md](./ARCHITECTURE.md)).

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

### 2. Initialize the project

```bash
cd /path/to/ed-tech-system-mcp

uv init --package --name mcp-server
```

This creates `pyproject.toml`. Update it to use a `src/` layout consistent with the architecture:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-server"
version = "0.1.0"
description = "Domain-Driven MCP server for ed-tech workflows"
readme = "ARCHITECTURE.md"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastmcp",
    "langchain",
    "langgraph",
    "pydantic>=2",
    "supabase",
    "duckduckgo-search",
    "google-api-python-client",
    "python-dotenv",
    "pydantic-settings",
]

[project.scripts]
mcp-server = "mcp_server.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/mcp_server"]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
    "mypy",
    "httpx",
]
```

### 3. Pin runtime dependencies (safest practice)

Add packages with `uv add` so both `pyproject.toml` and `uv.lock` stay in sync. For production stability, **pin direct dependencies to exact versions** after the initial resolve:

```bash
# Resolve and lock
uv lock

# Example: pin a direct dependency to a known-good version
uv add "fastmcp==3.4.4"
uv add "pydantic>=2.10,<3"
```

Review the generated `uv.lock` and commit it. Re-run `uv lock` whenever `pyproject.toml` changes.

### 4. Create the virtual environment and install

```bash
uv sync --all-groups
```

This creates `.venv/` beside `pyproject.toml` and installs exactly what is in `uv.lock`.

For production-like installs (runtime only):

```bash
uv sync --frozen --no-dev
```

| Flag | When to use |
| :--- | :--- |
| `--frozen` | CI and deployment — fail if lockfile is stale; install exact locked versions |
| `--locked` | Stricter CI gate — error if `pyproject.toml` and `uv.lock` are out of sync |
| `--all-groups` | Local development — includes `dev` dependency group |

### 5. Verify the environment

```bash
uv run python --version          # Expect: Python 3.12.x
uv run python -c "import fastmcp, pydantic, langchain; print('OK')"
uv run fastmcp version           # Confirms MCP stack is wired correctly
```

---

## Secrets & safety

Secrets must **never** be committed to the repository. This section defines how to route configuration between a local `.env` file, `python-dotenv`, OS-level environment variables, and a secrets manager — without leaking credentials into git, logs, or MCP tool definitions.

### Golden rules

| Rule | Detail |
| :--- | :--- |
| **No env files in git** | Never commit `.env`, `.env.*`, `*.env`, or Doppler template files — use Doppler or a local gitignored `.env` only |
| **Single load point** | Load configuration **only** in `main.py` (Entrypoint). No `load_dotenv()` in Domain, Application, Interface, or Infrastructure |
| **Inject, don't import** | Pass secrets into Infrastructure adapters via constructors or a typed `Settings` object — never `os.getenv()` scattered across the codebase |
| **OS env wins** | When both a `.env` file and a real environment variable exist, the real environment variable must take precedence |
| **No secrets in MCP config** | Cursor/`mcp.json` may reference `${env:VAR}` placeholders — never paste literal keys into version-controlled JSON |
| **Fail closed** | If a required secret is missing at startup, exit immediately with a clear error — do not fall back to empty strings or mock credentials |

### Configuration routing strategy

Use **one interface** (`Settings`) and **route the source** based on where the process runs:

```text
                    ┌─────────────────────────────────────┐
                    │         Process starts (main.py)     │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │  Is APP_ENV / ENV set to            │
                    │  "production" or "ci"?                │
                    └─────────┬───────────────┬─────────────┘
                         yes  │               │ no
              ┌───────────────▼───┐   ┌───────▼────────────────┐
              │ Skip .env file     │   │ Load .env via dotenv   │
              │ entirely           │   │ (local dev only)       │
              └───────────────┬───┘   └───────┬────────────────┘
                              │               │
              ┌───────────────▼───────────────▼────────────────┐
              │  Read all values from os.environ               │
              │  (injected by secrets manager / CI / shell)    │
              └───────────────┬────────────────────────────────┘
                              │
              ┌───────────────▼────────────────────────────────┐
              │  Validate with Pydantic Settings               │
              │  → pass to Infrastructure adapters             │
              └────────────────────────────────────────────────┘
```

| Environment | `APP_ENV` | Secret source | Load `.env`? |
| :--- | :--- | :--- | :--- |
| **Local development** | `development` (default) | Gitignored `.env` in project root | **Yes** — via `python-dotenv` |
| **CI / automated tests** | `ci` | Doppler → GitHub sync, or platform secret store (e.g. GitHub Actions Secrets) | **No** |
| **Production / staging** | `production` / `staging` | Secrets manager (see below) | **No** |
| **Cursor / local MCP host** | `development` | Shell profile, OS keychain, or `.env` | **Yes** — dotenv fills gaps only |

Set `APP_ENV` explicitly in each context. Never rely on implicit detection of "am I in prod?" beyond this variable.

### Dotenv vs OS environment: precedence

`python-dotenv` is a **local-dev convenience**, not a secrets manager. Use it with strict settings so it cannot override injected secrets:

```python
# src/mcp_server/main.py  (Entrypoint only)
import os
from pathlib import Path

from dotenv import load_dotenv

def bootstrap_environment() -> None:
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "development":
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)

    # override=False → existing os.environ values always win.
    # CI, production, and MCP hosts that inject vars are never overwritten by .env.
```

| Call | Behavior | Use when |
| :--- | :--- | :--- |
| `load_dotenv(override=False)` | `.env` fills **missing** keys only | **Default — always use this** |
| `load_dotenv(override=True)` | `.env` overwrites existing env vars | **Never** in this project |
| Skip `load_dotenv()` | Only `os.environ` is read | `APP_ENV=ci` or `APP_ENV=production` |

Typed settings validation (recommended — add `pydantic-settings` as a runtime dependency):

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,       # dotenv is handled explicitly in bootstrap_environment()
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    youtube_api_key: SecretStr | None = Field(default=None, alias="YOUTUBE_API_KEY")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    llm_model: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Redis cache (Infrastructure) — optional; degrades when disabled or unavailable
    cache_enabled: bool = Field(default=False, alias="CACHE_ENABLED")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: SecretStr | None = Field(default=None, alias="REDIS_PASSWORD")
    cache_ttl_supabase_find_documents: int | None = Field(
        default=None, alias="CACHE_TTL_SUPABASE_FIND_DOCUMENTS"
    )
    cache_ttl_youtube_search_videos: int | None = Field(
        default=None, alias="CACHE_TTL_YOUTUBE_SEARCH_VIDEOS"
    )
    cache_ttl_web_search: int | None = Field(default=None, alias="CACHE_TTL_WEB_SEARCH")
    cache_ttl_mcp_tool: int | None = Field(default=None, alias="CACHE_TTL_MCP_TOOL")
    cache_ttl_llm_completion: int | None = Field(
        default=None, alias="CACHE_TTL_LLM_COMPLETION"
    )
    cache_key_prefix_supabase: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_SUPABASE")
    cache_key_prefix_youtube: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_YOUTUBE")
    cache_key_prefix_web: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_WEB")
    cache_key_prefix_mcp_tool: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_MCP_TOOL")
    cache_key_prefix_llm: str | None = Field(default=None, alias="CACHE_KEY_PREFIX_LLM")
```

See `src/mcp_server/settings.py` for the canonical `Settings` definition.

`SecretStr` prevents accidental logging of key values via `str(settings.supabase_service_role_key)`.

When `CACHE_ENABLED=false`, adapters are not wrapped and no Redis connection is attempted. When enabled but Redis is unreachable, cache operations are skipped and delegates are called directly (graceful degradation).

#### Production cache requirement

In **staging** and **production** (`APP_ENV=staging` or `APP_ENV=production`), enable the shared cache store so Supabase, YouTube, web search, MCP tool I/O, and LLM completions share one Redis instance at the composition root:

| Variable | Production value | Notes |
| :--- | :--- | :--- |
| `CACHE_ENABLED` | `true` | Required for production deployments |
| `REDIS_URL` | Managed Redis endpoint | Prefer a single URL (e.g. `redis://:password@host:6379/0`) |
| `REDIS_HOST` / `REDIS_PORT` | Fallback when `REDIS_URL` unset | Use only when your platform injects host/port separately |

**Deployment checklist (Doppler / secrets manager):**

1. Provision a managed Redis instance (TLS URL if your provider requires it).
2. Add `CACHE_ENABLED=true` and `REDIS_URL` to the `stg` and `prd` Doppler configs (or cloud secret store).
3. Sync secrets to your runtime (e.g. `doppler run -- uv run mcp-server` or platform injection) — never commit Redis credentials.
4. For local development, copy the variable names above into a gitignored `.env` (or use `doppler run`). A `.env.example` file may exist on disk for convenience but is **not version-controlled** — `.gitignore` excludes `*.env.*`, so the committed production cache checklist lives in this section and in Doppler bootstrap scripts only.
5. Verify graceful degradation: if Redis is down, the server continues serving requests without cache (cache reads return miss; writes are skipped).

Local development may keep `CACHE_ENABLED=false` (default). CI tests run with cache disabled unless a dedicated Redis service is added to the workflow.

#### RAG settings (Phase A — shipped in `settings.py`)

See [INVESTIGATION1.md](changelog/2026-07-22/domain/INVESTIGATION1.md) for library and port design.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | fastembed model id |
| `EMBEDDING_DIMENSION` | `384` | Must match pgvector column |
| `EMBEDDING_WARM_ON_BOOT` | `false` | Pre-load ONNX at bootstrap |
| `EMBEDDING_CACHE_DIR` | `.cache/fastembed` | Model weights on VPS |
| `RETRIEVAL_MODE` | `hybrid` | `vector` or `hybrid` (MVP) |
| `RETRIEVE_LIMIT` | `20` | Pre-rerank candidate cap |
| `RERANK_ENABLED` | `false` | MVP default off |
| `RERANKER_MODEL` | `BAAI/bge-reranker-base` | When rerank enabled (MIT, fastembed ONNX) |
| `RERANK_TOP_N` | `6` | Post-rerank cap |
| `CACHE_TTL_EMBEDDING_QUERY` | `3600` | Query embedding cache TTL (seconds) |
| `CACHE_TTL_VECTOR_RETRIEVE` | `600` | Retrieval result cache TTL (seconds) |
| `CACHE_KEY_PREFIX_EMBEDDING` | `embed` | Redis key namespace |
| `CACHE_KEY_PREFIX_VECTOR` | `vector` | Redis key namespace |
| `VECTOR_STORE_BACKEND` | `auto` | `auto`, `chroma`, or `supabase` |
| `SUPABASE_VECTOR_ENABLED` | `false` | When `true`, `auto` selects Supabase pgvector |
| `CHROMA_PERSIST_PATH` | `.cache/chromadb` | Local Chroma persistence directory |
| `CHROMA_COLLECTION_NAME` | `document_chunks` | Chroma collection for chunk embeddings |

**Vector store default:** `VECTOR_STORE_BACKEND=auto` with `SUPABASE_VECTOR_ENABLED=false` uses **ChromaDB** locally until Supabase migrations are applied; set `SUPABASE_VECTOR_ENABLED=true` (or `VECTOR_STORE_BACKEND=supabase`) to switch.

**Blocked for commercial ed-tech:** `RERANKER_MODEL=jinaai/jina-reranker-v2-base-multilingual` (CC-BY-NC-4.0).

### Recommended secrets manager (by context)

Route secrets **into `os.environ` before the process starts** (or via your platform's injection). The application never reads directly from a secrets-manager SDK in Domain or Application code — only the Entrypoint/bootstrap layer resolves configuration.

| Context | Recommended tool | Why |
| :--- | :--- | :--- |
| **Local development** | Gitignored `.env` + `python-dotenv` | Simple, offline-friendly; file never enters git |
| **CI pipelines** | **Doppler → GitHub sync** (recommended for teams) or **GitHub Actions Encrypted Secrets** | Doppler is the single source of truth; sync pushes secrets to GitHub Actions automatically. Manual GitHub Secrets work for solo repos with no rotation needs |
| **Team / multi-environment** | **[Doppler](https://www.doppler.com/)** | CLI injects env vars at runtime (`doppler run -- uv run mcp-server`); central rotation, audit trail, no `.env` files on disk |
| **Cloud production** | **AWS Secrets Manager** or **GCP Secret Manager** | IAM-scoped access, automatic rotation, integrates with ECS/Lambda/Cloud Run |
| **Enterprise / self-hosted** | **HashiCorp Vault** | Fine-grained policies, dynamic secrets, on-prem option |

**Safest default for this project:**

1. **Local** — `.env` (gitignored), loaded with `override=False`, or `doppler run` for teams that prefer no secrets on disk.
2. **CI** — **Doppler → GitHub sync** (one source of truth; rotation in Doppler propagates to Actions), or manual GitHub Actions Secrets for solo repos.
3. **Shared / deployed** — **Doppler** (developer velocity + audit) or your cloud provider's secret manager (production hardening).

See [Doppler + GitHub integration](#doppler--github-integration) for the full setup.

Avoid storing production secrets in `.env` files on servers. Production containers and VMs should receive variables from the orchestrator or a `doppler run` / `aws secretsmanager get-secret-value` step in the entrypoint script — not from a file in the repo checkout.

### Local setup (never committed)

Create a private local `.env` in the project root (gitignored) with the [required environment variables](#required-environment-variables) below, or use Doppler:

```bash
# Option A — Doppler (recommended for teams)
doppler login
./scripts/doppler/setup-local.sh
doppler run -- uv run mcp-server

# Option B — local .env file (solo dev)
$EDITOR .env
```

Verify `.env` is ignored before your first commit:

```bash
git check-ignore -v .env   # must print a .gitignore rule
git status                 # .env must NOT appear as untracked
```

### `.gitignore` (minimum)

```gitignore
.venv/
.env
.env.*
*.env
*.env.*
scripts/doppler/*.env
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
*.egg-info/
```

### Operational configuration (`config.json`)

Non-secret workflow tuning lives in a **committed** `config.json` at the repository root (same path resolution as `.env` — see `operational_config.default_config_path()`). Secrets stay in environment variables via `Settings`; do not put API keys or credentials in `config.json`.

`main.py` loads and validates this file **after** `Settings` and **before** `create_mcp_server()`. A missing file, invalid JSON, or failed Pydantic validation aborts startup: `main` prints `Startup failed: …` to stderr and exits with code `1`.

| Key | Type | Unit | Validation | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `node_retries` | integer | count | `>= 0` | Retry count for LangGraph agent nodes |
| `workflow_timeout` | number | seconds | `> 0` | Overall LangGraph workflow execution limit |
| `agent_node_timeout` | number | seconds | `> 0` | Per-node execution limit |

Default values shipped in the repo:

```json
{
  "node_retries": 3,
  "workflow_timeout": 300,
  "agent_node_timeout": 60
}
```

To override locally, edit `config.json` in the project root. There is no environment-variable override in this increment — operational values are file-only. Loader and field units are documented in `src/mcp_server/operational_config.py`.

Startup order in `main.py`:

```text
bootstrap_environment() → load_settings() → configure_logging(settings)
  → load_operational_config() → initialize_application_runtime() → create_mcp_server() → server.run()
```

`LOG_LEVEL` is read from validated `Settings` and applied to the root logger via `logging.basicConfig()` immediately after settings load. Supported values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive). Unrecognized values fall back to `INFO`.

### Required environment variables

These keys are managed in **Doppler** (`ed-harness-system` project). For local-only work, create a gitignored `.env` with the same names:

```dotenv
# Runtime context: development | ci | staging | production
APP_ENV=development

# Supabase (Infrastructure)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Optional search provider (Infrastructure)
# TAVILY_API_KEY=

# YouTube Data API (Infrastructure — video search in documents)
YOUTUBE_API_KEY=

# Groq LLM (Application — LangGraph reasoning nodes)
GROQ_API_KEY=
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0

# Redis cache (Infrastructure — optional; disabled by default)
CACHE_ENABLED=false
# Prefer REDIS_URL when available:
# REDIS_URL=redis://localhost:6379/0
# Or configure host/port/password separately:
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_PASSWORD=
# Per-operation TTL overrides (seconds; omit to use defaults)
# CACHE_TTL_SUPABASE_FIND_DOCUMENTS=600
# CACHE_TTL_YOUTUBE_SEARCH_VIDEOS=3600
# CACHE_TTL_WEB_SEARCH=300
# CACHE_TTL_MCP_TOOL=60
# CACHE_TTL_LLM_COMPLETION=3600
# Per-operation key prefixes (optional)
# CACHE_KEY_PREFIX_SUPABASE=supabase
# CACHE_KEY_PREFIX_YOUTUBE=youtube
# CACHE_KEY_PREFIX_WEB=web
# CACHE_KEY_PREFIX_MCP_TOOL=mcp
# CACHE_KEY_PREFIX_LLM=llm

# RAG retrieval (Phase A — Infrastructure + Application)
# EMBEDDING_MODEL=intfloat/multilingual-e5-small
# EMBEDDING_DIMENSION=384
# EMBEDDING_WARM_ON_BOOT=false
# EMBEDDING_CACHE_DIR=.cache/fastembed
# RETRIEVAL_MODE=hybrid
# RETRIEVE_LIMIT=20
# RERANK_ENABLED=false
# RERANKER_MODEL=BAAI/bge-reranker-base
# RERANK_TOP_N=6
# BLOCKED (NC license): RERANKER_MODEL=jinaai/jina-reranker-v2-base-multilingual
# CACHE_TTL_EMBEDDING_QUERY=3600
# CACHE_TTL_VECTOR_RETRIEVE=600
# CACHE_KEY_PREFIX_EMBEDDING=embed
# CACHE_KEY_PREFIX_VECTOR=vector
# VECTOR_STORE_BACKEND=auto
# SUPABASE_VECTOR_ENABLED=false
# CHROMA_PERSIST_PATH=.cache/chromadb
# CHROMA_COLLECTION_NAME=document_chunks

# Logging
LOG_LEVEL=INFO
```

### Injecting secrets without committing them

#### CI (GitHub Actions)

When using **Doppler → GitHub sync** (recommended for teams), secrets are managed in Doppler and mirrored into GitHub automatically — you do not enter them manually in the GitHub UI. See [Doppler + GitHub integration](#doppler--github-integration).

For solo repos without Doppler, store each value under **Settings → Secrets and variables → Actions**. Reference them in the workflow — never echo or log them:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      APP_ENV: ci
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - run: uv sync --frozen --all-groups
      - run: uv run pytest
```

#### Doppler (team / deployed environments)

```bash
# Install Doppler CLI, authenticate once, link project config
doppler setup

# Run the MCP server with secrets injected into os.environ (no .env file on disk)
doppler run -- uv run mcp-server
```

#### Doppler + GitHub integration

Use Doppler as the **single source of truth** for secrets and connect it to GitHub so CI workflows receive the same values as local development — without duplicating keys in two UIs.

**Why integrate Doppler with GitHub**

| Benefit | Detail |
| :--- | :--- |
| **One place to rotate** | Update a key in Doppler; the GitHub sync pushes the new value to Actions secrets automatically |
| **Environment parity** | Map Doppler configs (`dev`, `github_ci`, `stg`, `prd`) to GitHub repo or environment secrets |
| **Audit trail** | Doppler logs who changed what and when; GitHub provides workflow run history |
| **No drift** | Avoid mismatches between a developer's `.env` and CI secrets |

**Prerequisites**

- A [Doppler](https://www.doppler.com/) project named **`ed-harness-system`** with the [required environment variables](#required-environment-variables) (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `YOUTUBE_API_KEY`, etc.)
- GitHub repository permissions to configure Actions secrets (and optionally organization secrets)

Bootstrap placeholder secrets from the repo templates:

```bash
doppler login
./scripts/doppler/setup-local.sh
./scripts/doppler/bootstrap-from-env-example.sh
```

> **Note:** Plain `doppler setup` opens an interactive picker and fails in IDE terminals (`Doppler Error: EOF`). Always use `./scripts/doppler/setup-local.sh` or pass `--project`, `--config`, and `--no-interactive` explicitly.

The script uploads placeholder values for `dev`, `github_ci`, `stg`, and `prd` configs into the `ed-harness-system` project.

**Recommended Doppler layout for this project**

| Doppler environment | Doppler config | Used by |
| :--- | :--- | :--- |
| `dev` | `dev` | Local `doppler run` / `doppler setup` |
| `GitHub` | `github_ci` | Synced to GitHub Actions secrets (`APP_ENV=ci`) |
| `stg` | `stg` | Staging deploy (`APP_ENV=staging`) |
| `prd` | `prd` | Production deploy (`APP_ENV=production`) |

Create the dedicated **GitHub** environment in Doppler: **Project → Options → Create Environment**, name it `GitHub`, place it after `dev`. Store CI-specific values (test Supabase project, read-only keys) in the `github_ci` config under that environment (Doppler requires the `github_` prefix for configs in this environment).

**Two integration patterns**

| Pattern | How it works | Prefer when |
| :--- | :--- | :--- |
| **1. Sync (recommended)** | Doppler GitHub App pushes secrets from a config into GitHub Actions secrets | Standard CI; workflows use `${{ secrets.VAR }}` as today; rotation is automatic |
| **2. Runtime fetch** | Workflow installs Doppler CLI and fetches secrets at job start via a service token | You want secrets fetched just-in-time and never stored in GitHub |

##### Pattern 1 — Doppler → GitHub sync (recommended)

1. In Doppler: **Integrations → GitHub → Authorize** the Doppler GitHub App for your account or organization.
2. Select which repositories Doppler may access.
3. **Set up integration:**
   - **Feature:** `Actions`
   - **Sync target:** Repository (or Organization for shared secrets across private repos)
   - **Repository:** `ed-tech-system-mcp` (or your fork)
   - **Config:** `github_ci` (under the `GitHub` environment)
   - Optional: enable **Sync unmasked secrets as variables** so non-sensitive values like `SUPABASE_URL` sync as GitHub **Variables** (visible in logs) while keys stay masked as secrets.
4. Click **Set Up Integration**. Doppler syncs all secrets in the chosen config to GitHub and adds `DOPPLER_*` metadata secrets.

After setup, **manage secrets only in Doppler**. GitHub secret values are write-only — edits made in the GitHub UI are not imported back and will be overwritten on the next Doppler sync.

**Multiple GitHub environments (public repos):** create GitHub environments (e.g. `ci`, `staging`) and add one Doppler sync per environment, each pointing at the matching Doppler config.

**Organization secrets:** when connected to a GitHub Organization, choose **Sync target → Organization** and scope to private or all repositories for secrets shared across multiple repos.

Your workflow stays the same — secrets arrive via GitHub's native `${{ secrets.* }}` syntax:

```yaml
# .github/workflows/ci.yml  (example — secrets sourced from Doppler sync)
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      APP_ENV: ci
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
      YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - run: uv sync --frozen --all-groups
      - run: uv run pytest
```

##### Pattern 2 — Runtime fetch in the workflow

Use this when you prefer not to store application secrets in GitHub at all — only a single `DOPPLER_TOKEN` (service token scoped to the `github_ci` config) lives in GitHub.

```yaml
# .github/workflows/ci.yml  (example — fetch secrets at runtime)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: dopplerhq/cli-action@v3

      - name: Run tests with Doppler-injected secrets
        run: uv sync --frozen --all-groups && uv run pytest
        env:
          DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN }}
          DOPPLER_PROJECT: ed-harness-system
          DOPPLER_CONFIG: github_ci
        # dopplerhq/cli-action exports secrets to the job environment;
        # wrap commands with doppler run if your runner does not auto-inject:
        # run: doppler run -- uv sync --frozen --all-groups && doppler run -- uv run pytest
```

Create the service token in Doppler: **Access → Service Tokens → Generate**, scope it to the `ci` config, store it as `DOPPLER_TOKEN` in GitHub (manually or via the sync integration's metadata).

##### Migrating existing GitHub Secrets into Doppler

GitHub does not expose secret values via API, so Doppler cannot pull them automatically. Options:

1. **Re-enter values in Doppler** (simplest) — copy from your password manager or provider dashboards into the `ci` config, then enable sync.
2. **One-time export workflow** — Doppler provides a `workflow_dispatch` job that uploads existing GitHub secrets into a Doppler config. See [Doppler's GitHub Actions docs](https://docs.doppler.com/docs/github-actions#importing-secrets-from-github-actions).

After migration, treat Doppler as canonical and disable manual GitHub secret edits.

##### Rules when using Doppler + GitHub

| Rule | Detail |
| :--- | :--- |
| **Doppler is canonical** | Add, rotate, and delete secrets in Doppler — not in GitHub Settings |
| **Use consistent variable names** | Use identical names (`SUPABASE_URL`, not `supabase-url`) so the same `Settings` object works everywhere |
| **Set `APP_ENV=ci` in workflows** | Ensures `main.py` skips `load_dotenv()` and reads only injected env vars |
| **Never log secrets** | Do not `print(os.environ)`, dump `Settings`, or use `set -x` around secret exports |
| **Rotate in one place** | Revoke the old key in Supabase/YouTube, update Doppler; sync propagates to GitHub |

In Cursor, point the MCP server command at Doppler instead of baking secrets into `mcp.json`:

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "command": "doppler",
      "args": ["run", "--", "uv", "--directory", "/absolute/path/to/ed-tech-system-mcp", "run", "mcp-server"],
      "env": {
        "APP_ENV": "development"
      }
    }
  }
}
```

#### Cursor without Doppler (local only)

Export secrets in your shell profile or use `${env:VAR}` so Cursor inherits them from the OS — not from a committed file:

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ed-tech-system-mcp", "run", "mcp-server"],
      "env": {
        "APP_ENV": "development",
        "SUPABASE_URL": "${env:SUPABASE_URL}",
        "SUPABASE_SERVICE_ROLE_KEY": "${env:SUPABASE_SERVICE_ROLE_KEY}",
        "YOUTUBE_API_KEY": "${env:YOUTUBE_API_KEY}"
      }
    }
  }
}
```

`${env:VAR}` reads from the **host OS environment**. Combine with a gitignored `.env` loaded by `main.py` when vars are not already set in the shell.

### Leak prevention checklist

| Guard | Command / action |
| :--- | :--- |
| Confirm `.env` is ignored | `git check-ignore -v .env` |
| Scan repo for committed secrets | `uv run pip install detect-secrets && detect-secrets scan` |
| Block commits with secrets | Husky pre-commit runs `scan-secrets.sh` (gitleaks or secretlint) |
| Block sensitive file commits | Husky pre-commit runs `block-sensitive-files.sh` (`.env`, credentials, keys) |
| Enforce layer boundaries | `npm run lint:architecture` or `uv run lint-imports` (pre-push + CI; does not block commits) |
| CI secret exposure | Never `print(os.environ)`, log `Settings` dumps, or use `set -x` around secret exports |
| Rotate on leak | Revoke Supabase service-role key and YouTube API key immediately; re-issue and update the secrets manager |

### Loading rules (summary)

1. `bootstrap_environment()` in `main.py` is the **only** place that calls `load_dotenv()`.
2. Use `load_dotenv(override=False)` and only when `APP_ENV=development`.
3. Validate all required keys through Pydantic `Settings` before starting the MCP server.
4. Pass `Settings` into Infrastructure constructors — Domain and Application layers never touch `os.environ` or `.env`.
5. Use the **Supabase service role key** only in server-side MCP processes, never in client-facing config.
6. In CI and production, inject secrets via the platform store or secrets manager — **never** copy `.env` to the runner or server.

---

## Day-to-day workflow

```bash
# Activate the environment (optional — uv run works without activation)
source .venv/bin/activate

# Run the MCP server entrypoint
uv run mcp-server

# Add a new runtime dependency (updates lockfile automatically)
uv add some-package

# Add a dev-only tool
uv add --group dev some-dev-tool

# Upgrade a single package safely
uv lock --upgrade-package fastmcp

# Run tests
uv run pytest

# Lint
uv run ruff check src/
uv run ruff format --check src/
```

After pulling changes:

```bash
uv sync --frozen
```

If `pyproject.toml` or `uv.lock` changed, this reinstalls the exact locked graph.

---

## Git hooks (two-tier safety)

| Tier | Hook | Blocks | Checks |
| :--- | :--- | :--- | :--- |
| **1 — Safety** | Husky `pre-commit` | **Commits** | `.gitignore` probes + tracked violations (`verify-gitignore.sh`), tracked sensitive files (`check-tracked-sensitive.sh`), staged sensitive filenames (`block-sensitive-files.sh`), entropy heuristic (`scan-entropy.sh`), secret scan (`scan-secrets.sh` — gitleaks + secretlint when available) |
| **2 — Safety + Architecture** | Husky `pre-push`, pytest, CI | **Push / CI** (not commits) | Re-run `verify-gitignore.sh` + `check-tracked-sensitive.sh` + `scan-push-secrets.sh` (`pre-push-safety.sh`), then `import-linter` layer contracts + `check-boundary-patterns.sh` via `npm run lint:architecture` |

Install hooks after cloning (from the **repository root**):

```bash
npm install          # installs Husky via prepare script
npm run hooks:test   # dry-run Tier 1 pre-commit checks
npm run lint:architecture   # Tier 2 architecture linter
```

The same `hooks:test` and `lint:architecture` scripts are available from `ui/` when working on the React workflow UI.

---

## CI/CD safety checklist

Use this in GitHub Actions (or equivalent) for every push and PR. When using [Doppler + GitHub integration](#doppler--github-integration), CI secrets are synced from Doppler — no manual GitHub secret entry required.

```bash
uv sync --frozen --all-groups
uv run ruff check src/
uv run mypy src/
npm run lint:architecture
uv run pytest
```

| Check | Purpose |
| :--- | :--- |
| `uv sync --frozen` | Ensures CI uses committed lockfile hashes — no opportunistic upgrades |
| `npm run lint:architecture` | Enforces Clean Architecture import contracts and boundary anti-patterns |
| `--no-dev` in production deploy | Shrinks attack surface; runtime image contains only MCP server dependencies |
| Pin `uv` version in CI | Prevents CI resolver changes from altering builds unexpectedly |

Example CI pin:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv self update 0.7.0   # pin to a known uv release in workflow YAML
```

---

## Cursor / MCP client integration

When registering this server in Cursor (or any MCP host), point the client at the **project interpreter**, not the system Python. For secret injection patterns (`.env`, Doppler, `${env:VAR}`), see [Secrets & safety](#secrets--safety).

**Option A — uv launcher + OS env substitution (local dev):**

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ed-tech-system-mcp", "run", "mcp-server"],
      "env": {
        "APP_ENV": "development",
        "SUPABASE_URL": "${env:SUPABASE_URL}",
        "SUPABASE_SERVICE_ROLE_KEY": "${env:SUPABASE_SERVICE_ROLE_KEY}",
        "YOUTUBE_API_KEY": "${env:YOUTUBE_API_KEY}"
      }
    }
  }
}
```

**Option B — direct venv Python (when secrets come from gitignored `.env` via `main.py`):**

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "command": "/absolute/path/to/ed-tech-system-mcp/.venv/bin/python",
      "args": ["-m", "mcp_server.main"],
      "env": {
        "APP_ENV": "development"
      }
    }
  }
}
```

With Option B, leave secret keys out of `mcp.json` entirely — `main.py` loads them from the gitignored `.env` when `APP_ENV=development`.

**Option C — Doppler (team / no secrets on disk):** see [Doppler (team / deployed environments)](#doppler-team--deployed-environments) and [Doppler + GitHub integration](#doppler--github-integration) for CI sync.

Never paste literal API keys into version-controlled MCP configuration files.

---

## Supply-chain safety

| Practice | Detail |
| :--- | :--- |
| **Install from PyPI only** | Do not use `--index-url` mirrors unless your organization audits them |
| **Commit `uv.lock`** | Contains version pins and integrity hashes for transitive dependencies |
| **Review lockfile diffs** | Treat dependency bumps like code changes — read changelogs for `fastmcp`, `langchain`, and `supabase` |
| **Avoid `pip install -e .` on production hosts** | Use `uv sync --frozen --no-dev` in deployment |
| **No `sudo pip`** | Never install project dependencies as root or into system site-packages |
| **Periodic audits** | Run `uv pip audit` (or `pip-audit` via `uv run`) on a schedule |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `ModuleNotFoundError` for `mcp_server` | Wrong interpreter or missing sync | `uv sync --frozen` from repo root |
| Lockfile out of date | `pyproject.toml` edited manually | `uv lock` then commit `uv.lock` |
| Wrong Python version | OS `python3` is not 3.12 | `uv python install 3.12` then `uv sync` |
| Stale `.venv` after branch switch | Environment not rebuilt | `rm -rf .venv && uv sync --frozen` |
| MCP client cannot find server | Client uses system Python | Point `command` at `.venv/bin/python` or `uv run` |
| `Startup failed` on launch (config) | Missing or invalid `config.json` | Ensure repo-root `config.json` exists with all three keys and positive timeout values |

---

## Quick reference

```bash
# First-time setup
uv python install 3.12
uv sync --all-groups

# Daily development
uv sync --frozen
uv run mcp-server

# Production install
uv sync --frozen --no-dev
```

**Golden rule:** if it is not in `uv.lock`, it is not in your environment.
