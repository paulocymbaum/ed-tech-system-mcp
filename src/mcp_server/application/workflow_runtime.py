"""Runtime accessor for the wired document-video workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.cache import ICacheStore

_runtime_workflow: DocumentVideoWorkflow | None = None
_lazy_settings: WorkflowSettings | None = None
_lazy_cache_store: ICacheStore | None = None
_workflow_builder: WorkflowBuilder | None = None


class WorkflowSettings(Protocol):
    """Settings subset required to build the document-video workflow."""


WorkflowBuilder = Callable[[WorkflowSettings, ICacheStore | None], DocumentVideoWorkflow]


def register_document_video_workflow_builder(builder: WorkflowBuilder) -> None:
    """Register the composition-root workflow builder (wiring only)."""
    global _workflow_builder
    _workflow_builder = builder


def reset_document_video_workflow_builder() -> None:
    """Clear the registered workflow builder (for tests)."""
    global _workflow_builder
    _workflow_builder = None


def configure_lazy_document_video_workflow(
    settings: WorkflowSettings | None,
    cache_store: ICacheStore | None = None,
) -> None:
    """Store settings and cache for deferred workflow construction at first access."""
    global _lazy_settings, _lazy_cache_store, _runtime_workflow
    _lazy_settings = settings
    _lazy_cache_store = cache_store
    _runtime_workflow = None


def set_document_video_workflow(workflow: DocumentVideoWorkflow | None) -> None:
    """Store the wired workflow for application and interface consumers."""
    global _runtime_workflow
    _runtime_workflow = workflow


def get_document_video_workflow() -> DocumentVideoWorkflow | None:
    """Return the workflow, building lazily on first access when configured."""
    global _runtime_workflow
    if _runtime_workflow is not None:
        return _runtime_workflow
    if _lazy_settings is None or _workflow_builder is None:
        return None
    _runtime_workflow = _workflow_builder(_lazy_settings, _lazy_cache_store)
    return _runtime_workflow


def reset_document_video_workflow() -> None:
    """Clear the runtime workflow and lazy-init state (for tests)."""
    global _runtime_workflow, _lazy_settings, _lazy_cache_store
    _runtime_workflow = None
    _lazy_settings = None
    _lazy_cache_store = None
