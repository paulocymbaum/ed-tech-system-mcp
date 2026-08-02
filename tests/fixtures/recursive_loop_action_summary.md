# Recursive loop test fixture

## Action summary

| ID | Action | Type | Location | Severity | Effort | Blocked by | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RF01 | Delete Vercel serverless entrypoint | REMOVE | `src/mcp_server/vercel_app.py` | High | trivial | — | PENDING |
| RF02 | Delete slim Vercel wiring shim | REMOVE | `src/mcp_server/vercel_wiring.py` | High | trivial | RF01 | PENDING |
| RF03 | Delete Vercel platform config | REMOVE | `vercel.json` | High | trivial | — | PENDING |
| RF30 | Defer live Doppler secret upload | DEFER | Doppler dashboard | — | — | User approval | DEFER |
