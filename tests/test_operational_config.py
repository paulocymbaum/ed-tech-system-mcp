"""Operational config loading and runtime wiring tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mcp_server.application.workflow_config import (
    get_workflow_execution_config,
    reset_workflow_execution_config,
)
from mcp_server.operational_config import (
    OperationalConfig,
    default_config_path,
    load_operational_config,
)
from mcp_server.wiring import build_workflow_execution_config, initialize_application_runtime


@pytest.fixture(autouse=True)
def _reset_runtime_config() -> None:
    reset_workflow_execution_config()
    yield
    reset_workflow_execution_config()


def test_o01_load_operational_config_from_repo_root() -> None:
    config = load_operational_config()
    assert config.node_retries == 1
    assert config.validation_retries == 1
    assert config.workflow_timeout == 300
    assert config.agent_node_timeout == 60


def test_o02_load_operational_config_from_custom_path(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "node_retries": 1,
                "workflow_timeout": 120.5,
                "agent_node_timeout": 30,
            }
        ),
        encoding="utf-8",
    )
    config = load_operational_config(config_path)
    assert config.node_retries == 1
    assert config.workflow_timeout == 120.5
    assert config.agent_node_timeout == 30


def test_o03_operational_config_rejects_non_positive_timeouts() -> None:
    with pytest.raises(ValidationError):
        OperationalConfig(
            node_retries=1,
            workflow_timeout=0,
            agent_node_timeout=60,
        )
    with pytest.raises(ValidationError):
        OperationalConfig(
            node_retries=1,
            workflow_timeout=60,
            agent_node_timeout=-1,
        )


def test_o04_operational_config_rejects_negative_retries() -> None:
    with pytest.raises(ValidationError):
        OperationalConfig(
            node_retries=-1,
            workflow_timeout=60,
            agent_node_timeout=30,
        )


def test_o05_initialize_application_runtime_sets_workflow_config() -> None:
    operational = OperationalConfig(
        node_retries=2,
        workflow_timeout=90,
        agent_node_timeout=15,
    )
    runtime = initialize_application_runtime(operational)
    expected = build_workflow_execution_config(operational)
    assert runtime.workflow_execution_config == expected
    assert get_workflow_execution_config() == expected


def test_o06_get_workflow_execution_config_requires_initialization() -> None:
    with pytest.raises(RuntimeError, match="not been initialized"):
        get_workflow_execution_config()


def test_o08_operational_config_allows_zero_retries() -> None:
    config = OperationalConfig(
        node_retries=0,
        workflow_timeout=60,
        agent_node_timeout=30,
    )
    assert config.node_retries == 0


def test_o09_build_workflow_execution_config_maps_field_names() -> None:
    operational = OperationalConfig(
        node_retries=4,
        workflow_timeout=180.5,
        agent_node_timeout=45.25,
    )
    runtime = build_workflow_execution_config(operational)
    assert runtime.node_retries == 4
    assert runtime.validation_retries == 1
    assert runtime.workflow_timeout_seconds == 180.5
    assert runtime.agent_node_timeout_seconds == 45.25


def test_o10_default_config_path_points_to_repo_root_config() -> None:
    path = default_config_path()
    assert path.name == "config.json"
    assert path.is_file()


def test_o11_load_operational_config_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_operational_config(missing)


def test_o12_load_operational_config_missing_keys_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_operational_config(config_path)
