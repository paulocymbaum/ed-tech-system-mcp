# Vercel deployment (workflow UI)

The **workflow explorer UI** (`ui/`) deploys to **Vercel** as a **static SPA**. Production deploys run in GitHub Actions (prebuilt output). The FastAPI workflow API remains **local dev tooling** — see [OBSERVABILITY.md](./OBSERVABILITY.md).

---

## What ships on Vercel

| Component | On Vercel | Local dev |
| :--- | :--- | :--- |
| React UI (`ui/dist`) | Yes | `npm --prefix ui run dev` |
| FastAPI `/api` (SSE, runs) | No | `./scripts/dev/run-workflow-ui.sh` |

To point the hosted UI at a remote API, set **`VITE_API_BASE`** at build time (Doppler `github_ci` → GitHub variable, or workflow env). Empty value uses same-origin `/api` (works locally via Vite proxy only).

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
# Token from Doppler dev config (never commit)
export VERCEL_TOKEN="$(doppler secrets get VERCEL_TOKEN --plain)"
doppler run -- npx vercel link --yes
```

This writes `.vercel/project.json` (gitignored). Copy `orgId` and `projectId` into Doppler:

```bash
# Example — use your linked project.json values in the Doppler dashboard or:
doppler secrets set VERCEL_ORG_ID="..." VERCEL_PROJECT_ID="..." --project ed-harness-system --config dev
```

Repeat for `github_ci`, `stg`, and `prd` (same project IDs; token is account-scoped).

Create a token at [vercel.com/account/tokens](https://vercel.com/account/tokens) if needed; store as `VERCEL_TOKEN` in Doppler only.

### C. GitHub Actions secrets

**Recommended:** Doppler → Integrations → GitHub → sync `github_ci` config (see [ENVIRONMENT_SETUP.md](./ENVIRONMENT_SETUP.md#doppler--github-integration)).

**One-time manual sync** (until GitHub App sync is enabled):

```bash
./scripts/doppler/sync-vercel-to-github.sh
```

| Doppler key | GitHub secret | Purpose |
| :--- | :--- | :--- |
| `VERCEL_TOKEN` | `VERCEL_TOKEN` | Deploy CLI auth |
| `VERCEL_ORG_ID` | `VERCEL_ORG_ID` | Team / account |
| `VERCEL_PROJECT_ID` | `VERCEL_PROJECT_ID` | Target project |

Verify (names only): `gh secret list --repo paulocymbaum/ed-tech-system-mcp`

---

## 2. Deploy workflow

File: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)

| Trigger | Action |
| :--- | :--- |
| Push to `main` | `safety` → `verify` → `deploy` jobs in [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) |
| `workflow_dispatch` | Same pipeline; deploy runs only on `main` |

The deploy job uses GitHub **`environment: production`** (for deployment URL tracking). Ensure a **production** environment exists in the repo settings (it may auto-create on first run). Repo-level `VERCEL_*` secrets from `sync-vercel-to-github.sh` are available to that environment by default; if you use environment-scoped secrets instead, set the same three keys on **production**.

Steps:

1. `npm ci && npm run build` in `ui/`
2. Copy `ui/dist/` to `.vercel/output/static/`
3. Write SPA `config.json` for prebuilt routing
4. `vercel deploy --prebuilt --prod`

---

## 3. Local preview

CI packages `ui/dist` into `.vercel/output/static` + `config.json` before `vercel deploy --prebuilt`; quick local deploys below pass `ui/dist` directly (equivalent output, different layout).

```bash
npm --prefix ui ci
npm --prefix ui run build
doppler run -- npx vercel deploy ui/dist
```

Production:

```bash
doppler run -- npx vercel deploy ui/dist --prod
```

---

## 4. Verify secrets (no values printed)

```bash
for k in VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID; do
  doppler secrets get "$k" --project ed-harness-system --config github_ci --plain >/dev/null \
    && echo "$k set in Doppler github_ci"
done
```

---

## 5. Troubleshooting

| Issue | Fix |
| :--- | :--- |
| Deploy fails: missing `VERCEL_*` | Fill Doppler `github_ci`, run `./scripts/doppler/sync-vercel-to-github.sh` |
| UI loads but runs fail | Expected without backend — set `VITE_API_BASE` to hosted API URL at build time |
| Wrong team/project | Re-run `vercel link`, update Doppler + sync GitHub |
| Double deploys | Use either GitHub Action **or** Vercel Git integration for production, not both |

---

## 6. Security

- Never commit `.env`, `.vercel/`, or token values
- Rotate `VERCEL_TOKEN` in Doppler; re-sync to GitHub
- Manage secrets only in Doppler after GitHub sync is enabled
