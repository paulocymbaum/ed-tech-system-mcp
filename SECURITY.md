# Security

## Reporting vulnerabilities

Please report security issues privately via [GitHub Security Advisories](https://github.com/paulocymbaum/ed-tech-system-mcp/security/advisories/new) rather than opening a public issue.

## ChromaDB (CVE-2026-45829)

**Status:** mitigated by dependency pin.

| Item | Detail |
| :--- | :--- |
| CVE | [CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) |
| Affected | ChromaDB Python `>=1.0.0, <=1.5.9` |
| Impact | Pre-authentication code injection via the HTTP server collections API when `trust_remote_code=true` |
| This repo | Uses **embedded** `chromadb.PersistentClient` only (local disk persistence). Does **not** expose Chroma's HTTP server. |
| Mitigation | `pyproject.toml` pins `chromadb>=0.6.3,<1.0.0` until a patched `1.x` release is available |

When Chroma publishes a fixed version, bump the pin and re-run the test suite (`tests/test_chroma_vector_retriever.py`).

## Secrets and hooks

See `ENVIRONMENT_SETUP.md`. Pre-commit and pre-push hooks scan for secrets; CI runs `gitleaks` on every push and pull request.

## Public-repo documentation

This repository is public. Do **not** add private-zone internals to tracked files: unpublished schema, tenant notes, production URLs, project IDs, or Doppler/staging path layouts beyond what is already in `ENVIRONMENT_SETUP.md`. Put ops detail in the private backend docs or gitignored `changelog/`.
