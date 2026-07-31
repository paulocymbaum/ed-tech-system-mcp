# Hosting the MCP server (Python layer)

Production hosting targets the **MCP HTTP transport** (`streamable-http`), not stdio. Local IDE integrations keep using `uv run mcp-server` with the default `MCP_TRANSPORT=stdio`.

---

## What runs in production

| Endpoint | Purpose |
| :--- | :--- |
| `GET /health` | Liveness probe (load balancers, Docker, Fly, Railway) |
| `POST /mcp` | MCP streamable HTTP transport (FastMCP default path) |

Tools exposed: `health_check`, `find_documents`, `search_youtube`, `run_workflow`.

---

## Quick start (Docker Compose)

Secrets via Doppler (recommended):

```bash
doppler run --config prd -- docker compose up --build
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
| `workflow-api` | 8877 | Workflow explorer API (`/api/*`) for Vercel UI |

```bash
doppler run --config prd -- docker compose up --build -d
```

- MCP clients: `http://localhost:8000/mcp`
- Workflow API (point `VITE_API_BASE` here): `http://localhost:8877`

---

## Workflow API + Vercel UI

1. Host `workflow-api` with HTTPS (port 8877 behind reverse proxy).
2. Set `WORKFLOW_UI_CORS_ORIGINS` to your Vercel production URL.
3. Set GitHub variable `VITE_API_BASE` to the public API URL.
4. Push to `main` to rebuild the Vercel UI.

See [VERCEL.md](./VERCEL.md) for the full Vercel wiring checklist.

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
| `WORKFLOW_UI_CORS_ORIGINS` | (localhost only) | `https://your-app.vercel.app` |
| `WORKFLOW_UI_ALLOW_VERCEL_PREVIEWS` | `true` | `true` |
| `FASTMCP_MASK_ERROR_DETAILS` | `false` | `true` (set in Dockerfile) |
| `SUPABASE_URL` | required | required |
| `SUPABASE_SERVICE_ROLE_KEY` | required | required |
| `GROQ_API_KEY` | optional at boot | required for LLM workflows |
| `TAVILY_API_KEY` | optional | recommended |
| `YOUTUBE_API_KEY` | optional | recommended |

Store values in Doppler config **`prd`**; never commit `.env`.

---

## Deploy targets

| Platform | Approach |
| :--- | :--- |
| **Any VPS** | `docker compose up -d` behind nginx/Caddy TLS |
| **Fly.io** | `fly launch` using repo `Dockerfile`, set secrets, expose port 8000 |
| **Railway / Render** | Connect repo, use Dockerfile, inject Doppler or platform secrets |
| **Kubernetes** | Deployment + Service on port 8000, probe `GET /health` |

You do **not** need Kubernetes for a single instance. Docker (or a managed container platform) is enough.

---

## Client configuration

Point MCP clients that support HTTP transport at your hosted URL:

```json
{
  "mcpServers": {
    "ed-tech-system": {
      "url": "https://api.example.com/mcp"
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

docker compose ps
```

CI builds the Docker image on every `main` push (`Build MCP Docker image` job) to catch Dockerfile regressions.
