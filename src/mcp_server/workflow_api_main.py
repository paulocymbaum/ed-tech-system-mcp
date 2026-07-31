"""Production entrypoint for the hosted workflow API (Vercel UI backend)."""

from __future__ import annotations

import sys

import uvicorn

from mcp_server.main import bootstrap_application_runtime, bootstrap_environment


def main() -> None:
    """Start the workflow API for cross-origin Vercel UI clients."""
    try:
        bootstrap_environment()
        settings = bootstrap_application_runtime()
        uvicorn.run(
            "mcp_server.interface.local_ui.api:create_app",
            factory=True,
            host=settings.workflow_api_host,
            port=settings.workflow_api_port,
            reload=False,
        )
    except Exception as exc:
        print(f"Workflow API startup failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
