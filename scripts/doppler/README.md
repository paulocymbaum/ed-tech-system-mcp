# Doppler scripts

Scripts for linking the repo to Doppler and syncing secrets to GitHub / Render.

## Config layout (current stage)

| Doppler config | Role today | Used by |
| :--- | :--- | :--- |
| **`dev`** | **Single source of truth for app secrets** | Local `.env`, `doppler run`, **Render MCP runtime** |
| `github_ci` | Deploy credentials + CI | `RENDER_*` → GitHub Actions; Render API auth in sync script |
| `stg` | Reserved | Not wired yet |
| `prd` | Reserved | Future environment split |

```text
Doppler dev (SUPABASE_*, GROQ_*, …)
    ├── pull-local-env.sh  →  .env (local MCP)
    └── sync-dev-to-render.sh  →  Render Web Service env vars

Doppler github_ci (RENDER_DEPLOY_HOOK_URL, RENDER_SERVICE_URL, RENDER_API_KEY, RENDER_SERVICE_ID)
    ├── sync-render-to-github.sh  →  GitHub Actions secrets
    └── sync-dev-to-render.sh  →  Render API authentication
```

**Important:** Render production always receives `APP_ENV=production` even when secrets are read from `dev`. Local dev keeps `APP_ENV=development` in Doppler `dev`.

## Scripts

| Script | Purpose |
| :--- | :--- |
| `setup-local.sh` | Link repo to Doppler `dev` (non-interactive) |
| `bootstrap-from-env-example.sh` | Upload **empty** placeholders to all configs (first time only) |
| `pull-local-env.sh` | Write gitignored `.env` from Doppler **`dev`** |
| `upload-local-env.sh` | Push local `.env` → Doppler `dev` |
| **`sync-dev-to-render.sh`** | **Preflight + push `dev` secrets → Render Web Service** |
| `sync-prd-to-render.sh` | Deprecated wrapper → calls `sync-dev-to-render.sh` |
| `sync-render-to-github.sh` | Push `RENDER_*` from `github_ci` → GitHub Secrets |

## Render MCP sync (typical flow)

```bash
doppler login
./scripts/doppler/setup-local.sh

# Ensure dev has real values (dashboard or upload from .env)
./scripts/doppler/pull-local-env.sh

# Push dev secrets to Render (requires github_ci RENDER_API_KEY + RENDER_SERVICE_ID)
./scripts/doppler/sync-dev-to-render.sh

# Or trigger deploy hook from CI / Render dashboard
```

### Preflight behavior

`sync-dev-to-render.sh` validates **all** keys before writing **any** value to Render.

**Required in `dev`:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

**Required in `github_ci` for sync script:** `RENDER_API_KEY`, `RENDER_SERVICE_ID`

## Security

- Never commit `.env`, `.env.local`, or secret values.
- Never re-run `bootstrap-from-env-example.sh` after filling `dev`.
- `RENDER_*` tokens are for deploy/sync only; app API keys live in `dev`.
