"""Runtime workflow execution limits injected at startup."""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import RetryPolicy

_runtime_config: WorkflowExecutionConfig | None = None

READ_NODE_RETRY_POLICY = RetryPolicy(max_attempts=1)


def read_node_retry_policy() -> RetryPolicy:
    """Read-only external port nodes fail fast — no automatic retries."""
    return READ_NODE_RETRY_POLICY


@dataclass(frozen=True, slots=True)
class WorkflowExecutionConfig:
    """Application-layer view of operational retry and timeout settings."""

    node_retries: int
    workflow_timeout_seconds: float
    agent_node_timeout_seconds: float
    validation_retries: int = 1


# Numeric defaults match committed repo-root config.json. Wiring injects
# live OperationalConfig at startup via set_workflow_execution_config.
DEFAULT_WORKFLOW_EXECUTION_CONFIG = WorkflowExecutionConfig(
    node_retries=1,
    workflow_timeout_seconds=300.0,
    agent_node_timeout_seconds=60.0,
    validation_retries=1,
)


def set_workflow_execution_config(config: WorkflowExecutionConfig) -> None:
    """Store workflow runtime config for application-layer consumers."""
    global _runtime_config
    _runtime_config = config


def get_workflow_execution_config() -> WorkflowExecutionConfig:
    """Return the workflow runtime config initialized at startup."""
    if _runtime_config is None:
        msg = "Workflow execution config has not been initialized"
        raise RuntimeError(msg)
    return _runtime_config


def reset_workflow_execution_config() -> None:
    """Clear runtime config (for tests)."""
    global _runtime_config
    _runtime_config = None
