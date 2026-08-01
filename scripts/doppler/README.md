# Doppler scripts

Scripts for linking the repo to Doppler and syncing secrets to GitHub / Vercel.

## Config layout (current stage)

| Doppler config | Role today | Used by |
| :--- | :--- | :--- |
| **`dev`** | **Single source of truth for app secrets** | Local `.env`, `doppler run`, **Vercel MCP runtime** |
| `github_ci` | Deploy credentials + CI | `VERCEL_*` → GitHub Actions; Vercel CLI auth in sync script |
| `stg` | Reserved | Not wired yet |
| `prd` | Reserved | Not used for Vercel at this stage |

```text
Doppler dev (SUPABASE_*, GROQ_*, …)
    ├── pull-local-env.sh  →  .env (local MCP)
    └── sync-dev-to-vercel.sh  →  Vercel production env vars

Doppler github_ci (VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID)
    ├── sync-vercel-to-github.sh  →  GitHub Actions secrets
    └── sync-dev-to-vercel.sh  →  Vercel CLI authentication only
```

**Important:** Vercel production always receives `APP_ENV=production` even when secrets are read from `dev`. Local dev keeps `APP_ENV=development` in Doppler `dev`.

When you later split environments, point `sync-dev-to-vercel.sh` at `prd` via `DOPPLER_CONFIG=prd` and fill `prd` in the dashboard — do not commit secrets.

## Scripts

| Script | Purpose |
| :--- | :--- |
| `setup-local.sh` | Link repo to Doppler `dev` (non-interactive) |
| `bootstrap-from-env-example.sh` | Upload **empty** placeholders to all configs (first time only; **do not re-run** if `dev` has real values) |
| `pull-local-env.sh` | Write gitignored `.env` from Doppler **`dev`** |
| `upload-local-env.sh` | Push local `.env` → Doppler `dev` |
| **`sync-dev-to-vercel.sh`** | **Preflight + push `dev` secrets → Vercel production** |
| `sync-prd-to-vercel.sh` | Deprecated wrapper → calls `sync-dev-to-vercel.sh` |
| `sync-vercel-to-github.sh` | Push `VERCEL_*` from `github_ci` → GitHub Secrets |

## Vercel MCP sync (typical flow)

```bash
doppler login
./scripts/doppler/setup-local.sh

# Ensure dev has real values (dashboard or upload from .env)
./scripts/doppler/pull-local-env.sh   # optional: verify dev → .env

# Push dev secrets to Vercel (requires github_ci VERCEL_* for CLI auth)
./scripts/doppler/sync-dev-to-vercel.sh

# Redeploy
VERCEL_TOKEN=$(doppler secrets get VERCEL_TOKEN --project ed-harness-system --config github_ci --plain)
vercel deploy --prod --token="$VERCEL_TOKEN"
```

### Preflight behavior

`sync-dev-to-vercel.sh` validates **all** keys before writing **any** value to Vercel. If `SUPABASE_URL` is empty in `dev`, the script exits with an error and Vercel is left unchanged.

**Required in `dev`:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

**Optional in `dev`:** if set, synced to Vercel; if empty, skipped — `TAVILY_API_KEY`, `YOUTUBE_API_KEY`, `GROQ_API_KEY`

**Optional in `dev` (defaults applied when missing or empty):** `LLM_MODEL`, `MCP_TRANSPORT`, `MCP_STATELESS_HTTP`, `VECTOR_STORE_BACKEND`, `EXTERNAL_REQUEST_LIMIT_PER_MINUTE`, `LOG_LEVEL`, `LLM_TEMPERATURE`

## Security

- Never commit `.env`, `.env.local`, or secret values.
- Never re-run `bootstrap-from-env-example.sh` after filling `dev` — it overwrites with empty placeholders.
- `VERCEL_*` tokens are for deploy/sync only; app API keys live in `dev` and are copied to Vercel by the sync script.
