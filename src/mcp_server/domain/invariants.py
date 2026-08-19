"""Pure domain invariant checks shared by adapters and workflows."""

from __future__ import annotations

from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError
from mcp_server.domain.schemas import ChunkRetrievalFilter


def require_non_empty_text(value: str, *, field: str) -> str:
    """Return stripped text or raise when the value is blank."""
    stripped = value.strip()
    if not stripped:
        msg = f"{field} must not be empty"
        raise DomainValidationError(msg)
    return stripped


def require_positive_int(value: int, *, field: str) -> int:
    """Return the value or raise when it is not positive."""
    if value <= 0:
        msg = f"{field} must be positive, got {value}"
        raise DomainValidationError(msg)
    return value


def require_credential(value: str, *, resource: str) -> str:
    """Return credential text or raise when integration credentials are missing."""
    stripped = value.strip()
    if not stripped:
        msg = f"{resource} credentials are not configured"
        raise ResourceNotFoundError(msg)
    return stripped


def require_tenant_retrieval_filter(filters: ChunkRetrievalFilter) -> ChunkRetrievalFilter:
    """Refuse unscoped chunk retrieval — tenant_id is mandatory."""
    tenant_id = (filters.tenant_id or "").strip()
    if not tenant_id:
        msg = "tenant_id is required for chunk retrieval"
        raise DomainValidationError(msg)
    filters.tenant_id = tenant_id
    return filters
