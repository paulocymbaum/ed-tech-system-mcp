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

# MCP clients: https://<service>.onrender.com/mcp
```

---

## 5. Free tier caveats

- Service **sleeps after ~15 min idle** — first request after sleep can take 30–60+ seconds.
- **512 MB RAM** may be tight; upgrade to Starter if OOM on cold start.
- Docker builds can take 5–15 minutes on first deploy.

---

## 6. Troubleshooting

| Issue | Fix |
| :--- | :--- |
| `/health` 500 after deploy | Set `SUPABASE_*` in Render env; check service logs |
| CI deploy skipped | Add `RENDER_DEPLOY_HOOK_URL` to GitHub secrets |
| OOM on startup | Upgrade Render plan or reduce memory-heavy imports at boot |
| Cold start timeout | Retry after wake-up; consider paid always-on plan |

---

## 7. Security

- Never commit `.env` or token values
- App secrets: Doppler **`dev`** only (synced to Render by script when enabled)
- Deploy hook URL: Doppler **`github_ci`** → GitHub Secrets only
