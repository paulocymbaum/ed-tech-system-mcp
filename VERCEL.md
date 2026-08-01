# Vercel deployment (Python MCP)

The **MCP server** deploys to **Vercel** as a **Python serverless function** on every push to `main`. The workflow UI (`ui/`) is optional and can be hosted separately.

Vercel installs only the **slim base dependencies** from `pyproject.toml` (no LangGraph, Chroma, or fastembed). Heavy workflow/RAG stacks install via the `full` extra for Docker only.

---

## Secrets model (current stage)

**Doppler `dev` is the single source of truth** for app secrets (local MCP and Vercel MCP).

| Secret type | Doppler config | Destination |
| :--- | :--- | :--- |
| App runtime (`SUPABASE_*`, `GROQ_*`, …) | **`dev`** | Local `.env` + **Vercel production** |
| Deploy CLI (`VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`) | **`github_ci`** | GitHub Actions + Vercel sync script auth |

`prd` / `stg` are reserved for a later environment split. Do not use them for Vercel until documented otherwise.

Full script reference: [scripts/doppler/README.md](./scripts/doppler/README.md)

---

## Dependency split

| Install target | Command | Includes |
| :--- | :--- | :--- |
| **Vercel MCP** (auto) | `pip install .` from `pyproject.toml` base deps | fastmcp, supabase, YouTube client, redis |
| **Docker / local full** | `uv sync --extra full` | + langgraph, langchain-core, fastembed, chromadb, tiktoken |

### fastembed on Vercel?

**No — not on the MCP layer.** Your RAG vectors live in **Supabase pgvector**; embeddings are produced at ingest time (Docker/`rag` extra), not on each Vercel cold start.

### LangGraph on Vercel?

**No.** `run_workflow` is registered only in Docker/local (`custom_tools_workflow.py`). Vercel exposes `health_check`, `search_youtube`, and `find_documents` only.

---

## Architecture

```text
Doppler dev ──sync-dev-to-vercel.sh──▶  Vercel production env vars
     │
     └── pull-local-env.sh ──▶  .env (local)

MCP clients  ──▶  https://<project>.vercel.app/mcp
Health       ──▶  https://<project>.vercel.app/health
Status page  ──▶  https://<project>.vercel.app/status/
```

| Component | Host | Purpose |
| :--- | :--- | :--- |
| MCP (`/mcp`, `/health`) | **Vercel** (Python) | Primary — streamable HTTP MCP transport |
| Workflow API (`/api/*`) | **Docker** (`workflow-api`) | LangGraph runs, SSE benchmarks (optional) |
| React UI (`ui/dist`) | Secondary | Graph explorer — deploy separately if needed |

Entrypoint: `src.mcp_server.vercel_app:app` (see `pyproject.toml` `[tool.vercel]`).

---

## 1. One-time setup (Doppler-first)

### A. Bootstrap placeholders (first time only)

```bash
doppler login
./scripts/doppler/setup-local.sh
./scripts/doppler/bootstrap-from-env-example.sh
```

**Warning:** Do not re-run bootstrap after filling `dev` — it uploads empty placeholders and wipes real values.

### B. Fill secrets in Doppler `dev`

Use the [Doppler dashboard](https://dashboard.doppler.com) or push from a local `.env`:

```bash
./scripts/doppler/upload-local-env.sh   # .env → dev
```

Required for Vercel sync: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

### C. Link Vercel + store deploy credentials

```bash
export VERCEL_TOKEN="$(doppler secrets get VERCEL_TOKEN --project ed-harness-system --config github_ci --plain)"
doppler run -- npx vercel link --yes
```

Store `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` in Doppler **`github_ci`** (and `dev` if you use them locally).

### D. Sync `dev` secrets to Vercel production

```bash
./scripts/doppler/sync-dev-to-vercel.sh
```

- Reads app secrets from Doppler **`dev`** (preflight — no partial writes)
- Reads `VERCEL_*` from **`github_ci`** for CLI auth
- Sets `APP_ENV=production` on Vercel (even though `dev` uses `development` locally)
- **Required in `dev`:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- **Optional API keys** (`TAVILY_*`, `YOUTUBE_*`, `GROQ_*`): synced only when set in `dev`; empty values are skipped
- **Optional with defaults** (`MCP_TRANSPORT`, `VECTOR_STORE_BACKEND`, …): applied when missing in `dev`
- No local `vercel link` required if `github_ci` has `VERCEL_*`

Legacy name `sync-prd-to-vercel.sh` delegates to the same script.

### E. GitHub Actions deploy credentials

```bash
./scripts/doppler/sync-vercel-to-github.sh
```

| Doppler key | GitHub secret | Purpose |
| :--- | :--- | :--- |
| `VERCEL_TOKEN` | `VERCEL_TOKEN` | Deploy CLI auth |
| `VERCEL_ORG_ID` | `VERCEL_ORG_ID` | Team / account |
| `VERCEL_PROJECT_ID` | `VERCEL_PROJECT_ID` | Target project |

---

## 2. Deploy workflow

File: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)

| Trigger | Action |
| :--- | :--- |
| Push to `main` | `safety` → `verify` → `deploy` (native Python build on Vercel) |
| `workflow_dispatch` | Same; deploy runs only on `main` |

**After changing Doppler `dev` secrets**, re-run `sync-dev-to-vercel.sh` and redeploy.

---

## 3. Local preview

```bash
doppler run --config dev -- vercel dev
```

Production CLI deploy:

```bash
doppler run --config dev -- vercel deploy --prod
```

---

## 4. Verify deployment

```bash
curl -sS "https://<project>.vercel.app/health"

# MCP clients: https://<project>.vercel.app/mcp
```

---

## 5. Troubleshooting

| Issue | Fix |
| :--- | :--- |
| Sync fails: empty `SUPABASE_URL` in `dev` | Fill secrets in Doppler **`dev`** (not `prd`) |
| Deploy fails: missing `VERCEL_*` | Fill Doppler `github_ci`, run `sync-vercel-to-github.sh` |
| `/health` 500 after deploy | Re-run `sync-dev-to-vercel.sh`, redeploy; check Vercel function logs |
| `vercel env pull` → `.env.local` | Vercel CLI metadata only; app secrets: `pull-local-env.sh` from **`dev`** |
| Partial Vercel env (only `APP_ENV`) | Old sync aborted mid-run; run `sync-dev-to-vercel.sh` (preflight fixes this) |

---

## 6. Security

- Never commit `.env`, `.vercel/`, or token values
- App secrets: Doppler **`dev`** only (synced to Vercel by script)
- Deploy tokens: Doppler **`github_ci`** → GitHub Secrets only
