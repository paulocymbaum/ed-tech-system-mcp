"""Entrypoint for the local-only workflow visualization server."""

from __future__ import annotations

import sys

import uvicorn

from mcp_server.interface.local_ui.api import assert_local_development, local_ui_host, local_ui_port


def main() -> None:
    """Start the local FastAPI workflow UI on loopback only."""
    try:
        assert_local_development()
        uvicorn.run(
            "mcp_server.interface.local_ui.api:create_app",
            factory=True,
            host=local_ui_host(),
            port=local_ui_port(),
            reload=True,
            reload_dirs=["src"],
        )
    except Exception as exc:
        print(f"Workflow UI startup failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
