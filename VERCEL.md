# Vercel deployment (Python MCP)

The **MCP server** deploys to **Vercel** as a **Python serverless function** on every push to `main`. The workflow UI (`ui/`) is optional and can be hosted separately.

Vercel installs only the **slim base dependencies** from `pyproject.toml` (no LangGraph, Chroma, or fastembed). Heavy workflow/RAG stacks install via the `full` extra for Docker only.

---

## Dependency split

| Install target | Command | Includes |
| :--- | :--- | :--- |
| **Vercel MCP** (auto) | `pip install .` from `pyproject.toml` base deps | fastmcp, supabase, YouTube client, redis |
| **Docker / local full** | `uv sync --extra full` | + langgraph, langchain-core, fastembed, chromadb, tiktoken |

### fastembed on Vercel?

**No — not on the MCP layer.** Your RAG vectors live in **Supabase pgvector**; embeddings are produced at ingest time (Docker/`rag` extra), not on each Vercel cold start. fastembed pulls ~100MB ONNX models and is a poor fit for serverless. If you later need query-time embeddings on Vercel, use a hosted embedding API (e.g. Supabase AI / external HTTP) rather than bundling ONNX.

### LangGraph on Vercel?

**No.** `run_workflow` is registered only in Docker/local (`custom_tools_workflow.py`). Vercel exposes `health_check`, `search_youtube`, and `find_documents` only.

---

## Architecture

```text
MCP clients (IDE / agents)  ──▶  https://<project>.vercel.app/mcp
Health checks               ──▶  https://<project>.vercel.app/health
```

| Component | Host | Purpose |
| :--- | :--- | :--- |
| MCP (`/mcp`, `/health`) | **Vercel** (Python) | Primary — streamable HTTP MCP transport |
| Workflow API (`/api/*`) | **Docker** (`workflow-api`) | LangGraph runs, SSE benchmarks (optional) |
| React UI (`ui/dist`) | Secondary | Graph explorer — deploy separately if needed |

Entrypoint: `mcp_server.vercel_app:app` (see `pyproject.toml` `[tool.vercel]`).

---

## 1. One-time setup (Doppler-first)

### A. Bootstrap placeholders (if not done)

```bash
doppler login
./scripts/doppler/setup-local.sh
./scripts/doppler/bootstrap-from-env-example.sh
```

### B. Create / link the Vercel project

```bash
export VERCEL_TOKEN="$(doppler secrets get VERCEL_TOKEN --plain)"
doppler run -- npx vercel link --yes
```

Copy `orgId` and `projectId` into Doppler (`dev`, `github_ci`, `stg`, `prd`).

### C. Sync runtime secrets to Vercel

MCP needs Supabase, Groq, etc. at **runtime** on Vercel. Sync from Doppler `prd`:

```bash
./scripts/doppler/sync-prd-to-vercel.sh
```

This pushes `SUPABASE_URL`, `GROQ_API_KEY`, and other runtime keys to Vercel **production**. Deploy credentials (`VERCEL_*`) stay in Doppler `github_ci` only.

Alternatively, use [Doppler → Vercel integration](https://docs.doppler.com/docs/vercel) for ongoing sync.

### D. GitHub Actions secrets (deploy only)

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

The deploy job runs `vercel deploy --prod --yes` (no `--prebuilt`). Vercel installs Python deps from `pyproject.toml` and routes all traffic to the ASGI app.

---

## 3. Local preview

```bash
doppler run --config prd -- vercel dev
```

Production:

```bash
doppler run --config prd -- vercel deploy --prod
```

---

## 4. Verify deployment

```bash
curl -sS "https://<project>.vercel.app/health"
# {"status":"ok",...}

# MCP clients: point streamable HTTP transport at https://<project>.vercel.app/mcp
```

---

## 5. Troubleshooting

| Issue | Fix |
| :--- | :--- |
| Deploy fails: missing `VERCEL_*` | Fill Doppler `github_ci`, run `sync-vercel-to-github.sh` |
| `/health` OK but tools fail | Run `sync-prd-to-vercel.sh`; check Vercel → Settings → Environment Variables |
| Build timeout / size limit | Heavy deps (`chromadb`, `langgraph`) may exceed Vercel limits — use Docker MCP as fallback ([DEPLOY.md](./DEPLOY.md)) |
| Cold start slow | Expected on serverless; consider Pro plan for longer `maxDuration` (60s configured in `vercel.json`) |

---

## 6. Security

- Never commit `.env`, `.vercel/`, or token values
- Runtime secrets live in Vercel env vars (synced from Doppler `prd`)
- Deploy tokens live in Doppler `github_ci` → GitHub Secrets only
