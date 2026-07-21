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
| **Commit templates only** | Commit `.env.example` with empty values; never commit `.env`, `.env.local`, or `.env.production` |
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
| **CI / automated tests** | `ci` | Platform secret store (e.g. GitHub Actions Secrets) | **No** |
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
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
```

`SecretStr` prevents accidental logging of key values via `str(settings.supabase_service_role_key)`.

### Recommended secrets manager (by context)

Route secrets **into `os.environ` before the process starts** (or via your platform's injection). The application never reads directly from a secrets-manager SDK in Domain or Application code — only the Entrypoint/bootstrap layer resolves configuration.

| Context | Recommended tool | Why |
| :--- | :--- | :--- |
| **Local development** | Gitignored `.env` + `python-dotenv` | Simple, offline-friendly; file never enters git |
| **CI pipelines** | **GitHub Actions Encrypted Secrets** (or GitLab CI/CD variables, marked masked) | Native to the repo host; no extra vendor; audit log per workflow |
| **Team / multi-environment** | **[Doppler](https://www.doppler.com/)** | CLI injects env vars at runtime (`doppler run -- uv run mcp-server`); central rotation, audit trail, no `.env` files on disk |
| **Cloud production** | **AWS Secrets Manager** or **GCP Secret Manager** | IAM-scoped access, automatic rotation, integrates with ECS/Lambda/Cloud Run |
| **Enterprise / self-hosted** | **HashiCorp Vault** | Fine-grained policies, dynamic secrets, on-prem option |

**Safest default for this project:**

1. **Local** — `.env` (gitignored), loaded with `override=False`.
2. **CI** — GitHub Actions Secrets mapped to `env:` in the workflow YAML.
3. **Shared / deployed** — **Doppler** (developer velocity + audit) or your cloud provider's secret manager (production hardening).

Avoid storing production secrets in `.env` files on servers. Production containers and VMs should receive variables from the orchestrator or a `doppler run` / `aws secretsmanager get-secret-value` step in the entrypoint script — not from a file in the repo checkout.

### Local setup (never committed)

```bash
# One-time: create your private local file from the committed template
cp .env.example .env

# Edit .env with your real keys — this file is gitignored
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
!.env.example
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
*.egg-info/
```

### `.env.example` (committed template — no real values)

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

# Logging
LOG_LEVEL=INFO
```

### Injecting secrets without committing them

#### CI (GitHub Actions)

Store each value under **Settings → Secrets and variables → Actions**. Reference them in the workflow — never echo or log them:

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
| Block commits with secrets | Add [gitleaks](https://github.com/gitleaks/gitleaks) or `detect-secrets` to a pre-commit hook |
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

## CI/CD safety checklist

Use this in GitHub Actions (or equivalent) for every push and PR:

```bash
uv sync --frozen --all-groups
uv run ruff check src/
uv run mypy src/
uv run pytest
```

| Check | Purpose |
| :--- | :--- |
| `uv sync --frozen` | Ensures CI uses committed lockfile hashes — no opportunistic upgrades |
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

**Option C — Doppler (team / no secrets on disk):** see the Doppler example in [Secrets & safety](#injecting-secrets-without-committing-them).

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
