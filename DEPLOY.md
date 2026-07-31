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

## Environment variables (production)

| Variable | Default (local) | Production |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | `production` |
| `MCP_TRANSPORT` | `stdio` | `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | `0.0.0.0` |
| `MCP_PORT` | `8000` | `8000` |
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

## Workflow UI (optional, separate)

The LangGraph workflow explorer API (`workflow-ui`) is still local-dev oriented. To connect the Vercel UI to a hosted backend later, deploy FastAPI separately and set `VITE_API_BASE` when building `ui/`.

Priority for this repo: **host `mcp-server` first** (this document).

---

## Verify

```bash
curl -s http://localhost:8000/health
# {"status":"ok","service":"ed-tech-system-mcp"}

docker compose ps
```

CI builds the Docker image on every `main` push (`Build MCP Docker image` job) to catch Dockerfile regressions.
