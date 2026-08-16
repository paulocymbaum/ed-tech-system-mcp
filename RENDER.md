# Render deployment (Docker MCP)

The **MCP server** deploys to **Render** as a **Docker Web Service**. The same image as local `docker compose` runs the full stack (`uv sync --extra full`, `mcp-server` on port 8000).

---

## Secrets model

**Doppler `dev` is the single source of truth** for app secrets (local MCP and Render MCP).

| Secret type | Doppler config | Destination |
| :--- | :--- | :--- |
| App runtime (`SUPABASE_*`, `GROQ_*`, …) | **`dev`** | Local `.env` + **Render Web Service** |
| Deploy credentials (`RENDER_*`) | **`github_ci`** | GitHub Actions deploy hook / sync script auth |

`prd` / `stg` are reserved for a later environment split.

Full script reference: [scripts/doppler/README.md](./scripts/doppler/README.md)

---

## Architecture

```text
Doppler dev ──(future) sync-dev-to-render.sh──▶  Render Web Service env vars
     │
     └── pull-local-env.sh ──▶  .env (local)

GitHub main ──CI──▶  pytest + Docker build ──▶  Render deploy hook

MCP clients  ──▶  https://<service>.onrender.com/mcp
Health       ──▶  https://<service>.onrender.com/health
```

| Component | Host | Purpose |
| :--- | :--- | :--- |
| MCP (`/mcp`, `/health`) | **Render** (Docker) | Primary — streamable HTTP MCP transport |
| Workflow API (`/api/*`) | **Docker** (optional 2nd Render service) | LangGraph explorer API |
| React UI (`ui/dist`) | Optional static host | Graph explorer |

Entrypoint: `mcp-server` CLI via `Dockerfile` `CMD`.

---

## 1. One-time setup (Render dashboard)

1. Connect this GitHub repo in [Render](https://dashboard.render.com).
2. Create a **Web Service** from `render.yaml` (Blueprint) or manually:
   - **Runtime:** Docker
   - **Dockerfile:** `./Dockerfile`
   - **Port:** `8000`
   - **Health check path:** `/health`
3. Add environment variables in the dashboard (or wait for Doppler sync script):
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (required)
   - `YOUTUBE_API_KEY`, `GROQ_API_KEY`, `TAVILY_API_KEY` (optional)

---

## 2. GitHub Actions deploy

On push to `main`, CI (after tests pass):

1. Authenticates to Doppler via `DOPPLER_TOKEN` (synced from Doppler `github_ci`).
2. Runs `scripts/doppler/sync-dev-to-render.sh` — pushes runtime secrets from Doppler `dev` to the Render Web Service.
3. POSTs the deploy hook from `RENDER_DEPLOY_HOOK_URL` in Doppler `github_ci`.
4. Probes `/health` at `RENDER_SERVICE_URL` when configured.

Orchestration script: `scripts/ci/render-deploy.sh`

| Doppler config | Keys used in deploy |
| :--- | :--- |
| `dev` | `SUPABASE_*`, API keys, runtime tuning (→ Render env vars) |
| `github_ci` | `DOPPLER_TOKEN`, `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_HOOK_URL`, `RENDER_SERVICE_URL` |

One-time GitHub setup: enable Doppler → GitHub sync for config `github_ci`, or run:

```bash
./scripts/doppler/sync-render-to-github.sh
```

`DOPPLER_TOKEN` must be available to the deploy job (via Doppler sync integration).

---

## 3. Sync `dev` secrets to Render

```bash
./scripts/doppler/sync-dev-to-render.sh
```

Requires `RENDER_API_KEY` and `RENDER_SERVICE_ID` in Doppler `github_ci`. CI runs this automatically on every successful `main` deploy via `scripts/ci/render-deploy.sh`.

---

## 4. Verify deployment

```bash
curl -sS "https://<service>.onrender.com/health"
# {"status":"ok","service":"ed-tech-system-mcp"}

# Full RAG smoke (health + tools/list + find_documents + run_workflow):
MCP_BASE_URL="https://<service>.onrender.com" bash scripts/ci/mcp-smoke.sh

# MCP clients: https://<service>.onrender.com/mcp
```

---

## 4.1 RAG embedding model cache (server-side only)

Render containers use a **read-only root filesystem**. RAG **chunk** results are **not** cached in Redis on this MCP layer — Supabase/pgvector owns retrieval freshness.

What **is** cached server-side on the MCP host:

| Mechanism | Path / env | Purpose |
| :--- | :--- | :--- |
| Docker image bake | `/app/model-cache/fastembed` | ONNX model weights (`scripts/ci/warm_embedding_cache.py` at build) |
| Boot warm-up | `EMBEDDING_WARM_ON_BOOT=false` (free) | Lazy-load ONNX on first RAG request; `true` OOMs 512Mi at deploy |
| HF hub scratch | `HF_HOME=/tmp/hf`, `XDG_CACHE_HOME=/tmp` | Writable temp for any HuggingFace hub I/O |

Without `HF_HOME` / `XDG_CACHE_HOME`, fastembed falls back to `~/.cache/huggingface` on a read-only path → `find_documents` / `run_workflow` fail with 502/503.

**Do not** enable Redis caching for `vector.retrieve`, `supabase.find_documents`, or `embedding.query` on this service — `wiring.py` keeps those rules disabled regardless of `CACHE_ENABLED`.

---

## 5. Free tier caveats

- **512 MB RAM**: keep `EMBEDDING_WARM_ON_BOOT=false` and `RERANK_ENABLED=false`. Deploys with warm-on-boot get `update_failed` / `oomKilled` (seen 2026-08-12/13).
- **Auth:** `/health` is public (Render probe). `/mcp` requires `Authorization: Bearer $MCP_INBOUND_TOKEN`. Privileged tools also require `X-EdHarness-Caller-Jwt` (learner/manager access token — never `service_role`). Set `MCP_INBOUND_TOKEN` in Doppler `dev` before deploy or boot fails closed (`MCP_REQUIRE_INBOUND_TOKEN=true`).
- Service **sleeps after ~15 min idle** — first request after sleep can take 30–60+ seconds. Do not ping `/mcp` 24/7 or you will burn the 750 free instance-hours.

---

## 6. Troubleshooting

| Issue | Fix |
| :--- | :--- |
| `/health` 500 after deploy | Set `SUPABASE_*` in Render env; check service logs |
| `find_documents` / `run_workflow` 502 or 503 | Set `HF_HOME=/tmp/hf`, `XDG_CACHE_HOME=/tmp`; redeploy image with baked model (`EMBEDDING_CACHE_DIR=/app/model-cache/fastembed`) |
| `find_documents` slow on first request | Expected on free tier with warm-on-boot off (lazy ONNX load) |
| Deploy `update_failed` + `oomKilled` 512Mi | Set `EMBEDDING_WARM_ON_BOOT=false` in Render + Doppler `dev`, redeploy |
| CI deploy skipped | Add `RENDER_DEPLOY_HOOK_URL` to GitHub secrets |
| OOM on startup | Keep warm-on-boot off, or upgrade Render plan |
| Cold start timeout | Retry after wake-up; consider paid always-on plan |

---

## 7. Security

- Never commit `.env` or token values
- App secrets: Doppler **`dev`** only (synced to Render by script when enabled)
- Deploy hook URL: Doppler **`github_ci`** → GitHub Secrets only
- `MCP_INBOUND_TOKEN` is the only credential allowed in the MCP `Authorization` header (BFF → MCP)
- Learner JWTs travel in `X-EdHarness-Caller-Jwt` so they are not JSON-RPC tool arguments and are not logged
- `LOG_LEVEL=INFO` on Render; do not dump `Settings`, JWTs, or HTTP bodies
