"""Entrypoint bootstrap and Settings contract tests (T21–T25)."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from mcp_server.main import bootstrap_environment, configure_logging, main
from mcp_server.settings import Settings, load_settings


def test_t21_bootstrap_skips_dotenv_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with patch("mcp_server.env_bootstrap.load_dotenv") as mock_load:
        bootstrap_environment()
        mock_load.assert_not_called()


def test_t22_bootstrap_loads_dotenv_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    with patch("mcp_server.env_bootstrap.load_dotenv") as mock_load:
        bootstrap_environment()
        assert mock_load.call_count == 2
        first_path = mock_load.call_args_list[0].kwargs["dotenv_path"]
        second_path = mock_load.call_args_list[1].kwargs["dotenv_path"]
        assert first_path.name == ".env"
        assert second_path.name == ".env.local"
        for call in mock_load.call_args_list:
            assert call.kwargs.get("override") is False


def test_t23_settings_requires_supabase_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_t24_settings_loads_with_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    settings = load_settings()
    assert settings.supabase_url == "https://test.supabase.co"
    assert settings.supabase_service_role_key.get_secret_value() == "test-key"


def test_t25_settings_youtube_key_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    settings = load_settings()
    assert settings.youtube_api_key is None


def test_e01_main_startup_loads_operational_config_before_mcp_server() -> None:
    """Operational config and runtime init must complete before MCP server creation."""
    mock_server = MagicMock()
    mock_settings = MagicMock(spec=Settings)
    mock_settings.mcp_transport = "stdio"
    mock_settings.mcp_host = "127.0.0.1"
    mock_settings.mcp_port = 8000
    mock_settings.mcp_stateless_http = False
    mock_settings.mcp_host_origin_protection = None
    mock_settings.mcp_allowed_hosts = ""
    call_order: list[str] = []
    runtime_args: list[tuple[object, object]] = []

    def _track(name: str, *args: object, **kwargs: object) -> object:
        call_order.append(name)
        if name == "initialize_application_runtime":
            runtime_args.append((args[0], args[1]))
        return mock_server if name == "create_mcp_server" else None

    with (
        patch(
            "mcp_server.main.bootstrap_environment",
            side_effect=lambda: _track("bootstrap_environment"),
        ),
        patch(
            "mcp_server.main.load_settings",
            side_effect=lambda: _track("load_settings") or mock_settings,
        ),
        patch(
            "mcp_server.main.configure_logging",
            side_effect=lambda settings: _track("configure_logging", settings),
        ),
        patch(
            "mcp_server.main.load_operational_config",
            side_effect=lambda: _track("load_operational_config"),
        ),
        patch(
            "mcp_server.main.initialize_application_runtime",
            side_effect=lambda operational_config, settings: _track(
                "initialize_application_runtime", operational_config, settings
            ),
        ),
        patch(
            "mcp_server.main.create_mcp_server",
            side_effect=lambda: _track("create_mcp_server"),
        ),
    ):
        main()

    mock_server.run.assert_called_once_with(transport="stdio")
    assert call_order == [
        "bootstrap_environment",
        "load_settings",
        "configure_logging",
        "load_operational_config",
        "initialize_application_runtime",
        "create_mcp_server",
    ]
    assert len(runtime_args) == 1
    assert runtime_args[0][1] is mock_settings


def test_e02_main_boots_without_groq_key_when_llm_not_invoked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health-check-only boot path must not require GROQ_API_KEY at startup."""
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    mock_server = MagicMock()

    with patch("mcp_server.main.create_mcp_server", return_value=mock_server):
        main()

    mock_server.run.assert_called_once_with(transport="stdio")


def test_e03_configure_logging_applies_log_level_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = load_settings()
    configure_logging(settings)

    assert logging.getLogger().level == logging.DEBUG


def test_e04_configure_logging_falls_back_to_info_for_invalid_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")

    settings = load_settings()
    configure_logging(settings)

    assert logging.getLogger().level == logging.INFO


def test_e05_configure_logging_maps_log_level_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "warning")

    settings = load_settings()
    configure_logging(settings)

    assert logging.getLogger().level == logging.WARNING


def test_e06_local_ui_main_starts_uvicorn_without_eager_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local UI entrypoint starts uvicorn; runtime wiring happens in FastAPI lifespan."""
    from mcp_server.local_ui_main import main as local_ui_main

    with (
        patch("mcp_server.local_ui_main.assert_local_development") as mock_assert,
        patch("mcp_server.local_ui_main.uvicorn.run") as mock_uvicorn,
    ):
        local_ui_main()

    mock_assert.assert_called_once()
    mock_uvicorn.assert_called_once()
