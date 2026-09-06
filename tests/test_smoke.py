"""Smoke tests for package scaffolding."""


def test_import_package() -> None:
    import mcp_server

    assert mcp_server.__version__ == "0.1.0"


def test_import_layers() -> None:
    from mcp_server.application import agent
    from mcp_server.domain import exceptions, interfaces, schemas
    from mcp_server.infrastructure import tavily_search_client, youtube_client
    from mcp_server.interface import custom_tools, mcp_server, validation

    assert exceptions.DomainError is not None
    assert interfaces.ISearchClient is not None
    assert schemas.VideoResult is not None
    assert agent.ainvoke_with_workflow_timeout is not None
    assert tavily_search_client.TavilySearchClient is not None
    assert youtube_client.YouTubeDataApiClient is not None
    assert mcp_server.create_mcp_server is not None
    assert validation.VideoSearchRequest is not None
    assert custom_tools.health_check is not None


def test_bootstrap_environment_without_dotenv() -> None:
    from mcp_server.main import bootstrap_environment

    bootstrap_environment()
