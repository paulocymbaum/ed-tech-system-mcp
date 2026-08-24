# Security

## Reporting vulnerabilities

Please report security issues privately via [GitHub Security Advisories](https://github.com/paulocymbaum/ed-tech-system-mcp/security/advisories/new) rather than opening a public issue.

## Secrets and hooks

See `ENVIRONMENT_SETUP.md`. Pre-commit and pre-push hooks scan for secrets; CI runs `gitleaks` on every push and pull request.

## Public-repo documentation

This repository is public. Do **not** add private-zone internals to tracked files: unpublished schema, tenant notes, production URLs, project IDs, or Doppler/staging path layouts beyond what is already in `ENVIRONMENT_SETUP.md`. Put ops detail in the private backend docs or gitignored `changelog/`.
