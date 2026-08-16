"""Entrypoint — transport initialization and environment bootstrap."""

import logging
import sys

from mcp_server.domain.mcp_transport import build_mcp_run_kwargs
from mcp_server.env_bootstrap import bootstrap_environment
from mcp_server.interface.custom_tools import (  # noqa: F401
    find_documents,
    health_check,
    search_youtube,
)
from mcp_server.interface.custom_tools_agent_workflows import (  # noqa: F401
    content_generation,
    research_article,
)
from mcp_server.interface.custom_tools_authoring import (  # noqa: F401
    author_lesson_pipeline,
    generate_mock_test_structure,
    save_to_backend,
    search_graph_nodes,
    validate_lesson,
    validate_mock_test,
    validate_project,
    validate_quiz,
    validate_test_boilerplate_tool,
)
from mcp_server.interface.custom_tools_project_review import (  # noqa: F401
    collect_project_review_context,
    project_review,
)
from mcp_server.interface.custom_tools_socratic import socratic_tutor  # noqa: F401
from mcp_server.interface.custom_tools_workflow import run_workflow  # noqa: F401
from mcp_server.interface.mcp_server import create_mcp_server
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import Settings, load_settings
from mcp_server.wiring import initialize_application_runtime, shutdown_application_runtime_sync


def configure_logging(settings: Settings) -> None:
    """Apply root log level from validated settings."""
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
    logging.basicConfig(level=level, force=True)


def bootstrap_application_runtime() -> Settings:
    """Load settings, operational config, and wire the composition root."""
    settings = load_settings()
    configure_logging(settings)
    operational_config = load_operational_config()
    initialize_application_runtime(operational_config, settings)
    return settings


def main() -> None:
    """Bootstrap environment, validate settings, and start the MCP server."""
    bootstrap_environment()
    settings = bootstrap_application_runtime()
    server = create_mcp_server()
    server.run(
        **build_mcp_run_kwargs(
            transport=settings.mcp_transport,
            host=settings.mcp_host,
            port=settings.mcp_port,
            stateless_http=settings.mcp_stateless_http,
            host_origin_protection=settings.mcp_host_origin_protection,
            allowed_hosts=settings.mcp_allowed_hosts,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Startup failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutdown_application_runtime_sync()
