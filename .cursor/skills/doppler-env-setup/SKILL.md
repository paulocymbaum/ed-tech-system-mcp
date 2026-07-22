---
name: doppler-env-setup
description: >-
  Sets up environment variables safely using Doppler and repo scripts for
  ed-harness-system. Use when configuring secrets, running doppler setup,
  bootstrapping env values, local .env files, GitHub Actions secrets sync,
  or when the user mentions Doppler, APP_ENV, or environment setup.
---

# Doppler Environment Setup (Safety First)

## Principles

1. **Secrets never enter git** — all env files are gitignored; Husky rejects staged env files.
2. **Doppler is canonical** — add, rotate, and delete secrets in Doppler, not GitHub Settings.
3. **Inject, don't embed** — use `doppler run` or OS env; app reads `Settings` only at entrypoint.
4. **Fail closed** — missing required secrets must error at startup, not silently use empty strings.
5. **Least exposure** — never log, print, or paste secret values in chat, commits, or changelog.

## Doppler project layout

| Config | `APP_ENV` | Use |
| :--- | :--- | :--- |
| `dev` | `development` | Local development |
| `github_ci` | `ci` | GitHub Actions (sync target) |
| `stg` | `staging` | Staging deploy |
| `prd` | `production` | Production deploy |

Project slug: **`ed-harness-system`**

Required keys: `APP_ENV`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `YOUTUBE_API_KEY`, `LOG_LEVEL` (optional: `TAVILY_API_KEY`).

## Setup workflow

Copy and track progress:

```
- [ ] 1. Authenticate
- [ ] 2. Link repo (setup-local.sh)
- [ ] 3. Bootstrap placeholders (first time only)
- [ ] 4. Fill real values in Doppler dashboard
- [ ] 5. Verify run + git safety
```

### Step 1 — Authenticate

```bash
doppler login
doppler me   # must succeed before continuing
```

### Step 2 — Link repo

```bash
./scripts/doppler/setup-local.sh
```

Uses `--no-interactive` flags. **Never** use bare `doppler setup` in IDE terminals.

Override defaults only when needed:

```bash
DOPPLER_PROJECT=ed-harness-system DOPPLER_CONFIG=dev ./scripts/doppler/setup-local.sh
```

### Step 3 — Bootstrap placeholders (first time only)

```bash
./scripts/doppler/bootstrap-from-env-example.sh
```

Uploads **empty** placeholders to all four configs. Safe to re-run only when intentionally resetting structure — it overwrites Doppler values for those keys.

Creates `github_ci` config if missing (under `GitHub` environment; name must use `github_` prefix).

### Step 4 — Fill real values

In [Doppler dashboard](https://dashboard.doppler.com) → `ed-harness-system` → select config → set secrets.

**Do not:**
- Commit filled `.env` files
- Paste keys into `mcp.json`, workflow YAML, or agent chat
- Edit synced secrets in GitHub UI (Doppler overwrites on next sync)

**Solo dev fallback:** create a gitignored `.env` in repo root (never commit). Copy variable names from `ENVIRONMENT_SETUP.md` § Required environment variables.

### Step 5 — Verify

```bash
# Secrets inject correctly
doppler run -- printenv APP_ENV SUPABASE_URL LOG_LEVEL

# Run the server
doppler run -- uv run mcp-server

# Git safety
git check-ignore -v .env scripts/doppler/secrets.dev.env
bash scripts/hooks/verify-gitignore.sh
bash scripts/hooks/block-env-files.sh
```

## Running by context

| Context | Command |
| :--- | :--- |
| Local dev (Doppler) | `doppler run -- uv run mcp-server` |
| Local dev (`.env` file) | `uv run mcp-server` with gitignored `.env`, `APP_ENV=development` |
| Cursor MCP | `"command": "doppler"`, `"args": ["run", "--", "uv", "run", "mcp-server"]` |
| CI | GitHub sync from `github_ci` config; workflow sets `APP_ENV=ci` |

## GitHub integration

1. Doppler → Integrations → GitHub → authorize
2. Sync **Feature:** Actions, **Config:** `github_ci`
3. Manage secrets only in Doppler after sync is enabled

See `ENVIRONMENT_SETUP.md` § Doppler + GitHub integration.

## Agent safety checklist

Before finishing any secrets-related task:

- [ ] No env files added to git or left untracked-but-committable
- [ ] No secret values written to repo files, changelog, or chat
- [ ] User directed to Doppler dashboard for real credentials
- [ ] `setup-local.sh` used instead of interactive `doppler setup`
- [ ] `APP_ENV` matches the target environment
- [ ] Husky hooks (`verify-gitignore.sh`, `block-env-files.sh`) still pass

## Common errors

| Error | Fix |
| :--- | :--- |
| `Doppler Error: EOF` on setup | Use `./scripts/doppler/setup-local.sh` |
| `you must provide a token` | Run `doppler login` |
| `Could not find config 'ci'` | Use `github_ci`, not `ci` |
| Env file blocked on commit | Expected — values belong in Doppler or gitignored `.env` |

## References

- `ENVIRONMENT_SETUP.md` — full secrets routing and GitHub sync
- `scripts/doppler/setup-local.sh` — non-interactive project link
- `scripts/doppler/bootstrap-from-env-example.sh` — placeholder upload
- `scripts/hooks/block-env-files.sh` — pre-commit env file guard
