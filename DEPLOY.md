# Hosting the MCP server (Python layer)

Production hosting targets the **MCP HTTP transport** (`streamable-http`), not stdio. Local IDE integrations keep using `uv run mcp-server` with the default `MCP_TRANSPORT=stdio`.

**Recommended for MCP:** deploy to **Render** (Docker Web Service) — see [RENDER.md](./RENDER.md).

---

## What runs in production

| Endpoint | Purpose |
| :--- | :--- |
| `GET /health` | Liveness probe (load balancers, Docker, Render, Fly) |
| `POST /mcp` | MCP streamable HTTP transport (FastMCP default path) |

Tools exposed: `health_check`, `find_documents`, `search_youtube`, `run_workflow`.

---

## Quick start (Docker Compose)

Secrets via Doppler (recommended):

```bash
doppler run --config dev -- docker compose up --build
```

Or export `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, then:

```bash
docker compose up --build
```

MCP URL for clients: `http://localhost:8000/mcp`

---

## Docker Compose services

| Service | Port | Role |
| :--- | :--- | :--- |
| `mcp` | 8000 | MCP streamable HTTP (`/mcp`) for IDE clients |
| `workflow-api` | 8877 | Workflow explorer API (`/api/*`) |

```bash
doppler run --config dev -- docker compose up --build -d
```

- MCP clients: `http://localhost:8000/mcp`
- Workflow API (point `VITE_API_BASE` here): `http://localhost:8877`

---

## Workflow API + optional UI

1. Host `workflow-api` with HTTPS (port 8877 behind reverse proxy or second Render service).
2. Set `WORKFLOW_UI_CORS_ORIGINS` to your UI origin if you host the React app separately.
3. MCP on Render: `https://<service>.onrender.com/mcp`

See [RENDER.md](./RENDER.md) for MCP deployment and env sync.

---

## Environment variables (production)

| Variable | Default (local) | Production |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | `production` |
| `MCP_TRANSPORT` | `stdio` | `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | `0.0.0.0` |
| `MCP_PORT` | `8000` | `8000` |
| `WORKFLOW_API_HOST` | `0.0.0.0` | `0.0.0.0` |
| `WORKFLOW_API_PORT` | `8877` | `8877` |
| `WORKFLOW_UI_CORS_ORIGINS` | (localhost only) | `https://your-app.onrender.com` |
| `WORKFLOW_UI_ALLOW_PREVIEW_DEPLOYMENTS` | `true` | `true` |
| `FASTMCP_MASK_ERROR_DETAILS` | `false` | `true` (set in Dockerfile) |
| `SUPABASE_URL` | required | required |
| `SUPABASE_SERVICE_ROLE_KEY` | required | required |
| `GROQ_API_KEY` | optional at boot | required for LLM workflows |
| `TAVILY_API_KEY` | optional | recommended |
| `YOUTUBE_API_KEY` | optional | recommended |
| `EMBEDDING_CACHE_DIR` | `.cache/fastembed` | `/app/model-cache/fastembed` (Docker bake) |
| `EMBEDDING_WARM_ON_BOOT` | `false` | `false` on free Render (512Mi); `true` OOMs at deploy |
| `HF_HOME` | (unset) | `/tmp/hf` on Render |
| `XDG_CACHE_HOME` | (unset) | `/tmp` on Render |

Store values in Doppler config **`dev`**; never commit `.env`.

### Caching policy

| Cached on MCP server | Not cached on MCP server |
| :--- | :--- |
| ONNX model **weights** (`EMBEDDING_CACHE_DIR`, image bake) | RAG **chunks** / document hits |
| LLM completions, YouTube, web search (Redis; required when `APP_ENV` is staging/production) | Query embedding vectors in Redis |
| MCP tool I/O (Redis, when enabled) | Chunk retrieval results — backend (Supabase) owns this |

---

## Deploy targets

| Platform | Approach |
| :--- | :--- |
| **Render** (recommended) | Connect repo, use `render.yaml` / Dockerfile, set secrets |
| **Any VPS** | `docker compose up -d` behind nginx/Caddy TLS |
| **Fly.io** | `fly launch` using repo `Dockerfile`, set secrets, expose port 8000 |
| **Railway** | Connect repo, use Dockerfile, inject Doppler or platform secrets |

---

## Client configuration

Point MCP clients that support HTTP transport at your hosted URL:

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "url": "https://<service>.onrender.com/mcp"
    }
  }
}
```

Use HTTPS in production. Terminate TLS at your reverse proxy or platform edge.

---

## Verify workflow API

```bash
curl -s http://localhost:8877/api/health
# {"status":"ok","mode":"hosted","workflow_count":...}
```

---

## Verify MCP server

```bash
curl -s http://localhost:8000/health
# {"status":"ok","service":"ed-tech-system-mcp"}

# RAG smoke (before deploy):
doppler run --config dev -- docker compose up --build -d
MCP_BASE_URL=http://localhost:8000 bash scripts/ci/mcp-smoke.sh

docker compose ps
```

CI builds the Docker image on every `main` push (`Build MCP Docker image` job) and triggers Render deploy when `RENDER_DEPLOY_HOOK_URL` is configured.
