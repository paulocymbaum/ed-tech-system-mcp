"""Operational tuning loaded from config.json at startup.

Units:
- ``node_retries``: provider retry count for LangGraph LLM nodes (non-negative)
- ``validation_retries``: content-generation validation loop cap (non-negative)
- ``workflow_timeout``: seconds (overall LangGraph workflow execution limit)
- ``agent_node_timeout``: seconds (per-node execution limit)
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class OperationalConfig(BaseModel):
    """Non-secret operational settings for agent and workflow execution."""

    node_retries: int = Field(
        ge=0,
        description="Retry count for LangGraph provider/LLM nodes",
    )
    validation_retries: int = Field(
        default=1,
        ge=0,
        description="Validation-driven regenerate loops for content generation",
    )
    workflow_timeout: float = Field(
        gt=0,
        description="Overall workflow execution timeout in seconds",
    )
    agent_node_timeout: float = Field(
        gt=0,
        description="Per-node execution timeout in seconds",
    )


def default_config_path() -> Path:
    """Return the canonical repo-root config.json path."""
    return Path(__file__).resolve().parents[2] / "config.json"


def load_operational_config(path: Path | None = None) -> OperationalConfig:
    """Load and validate operational configuration from config.json."""
    config_path = path or default_config_path()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return OperationalConfig.model_validate(raw)
