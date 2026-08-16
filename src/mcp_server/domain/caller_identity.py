"""Port for verifying MCP caller identity without logging tokens."""

from __future__ import annotations

from typing import Protocol


class CallerIdentityPort(Protocol):
    """Resolve a user JWT to a user id and tenant membership."""

    def user_id_from_jwt(self, caller_jwt: str) -> str:
        """Return the auth user id or raise DomainAuthorizationError."""

    def is_tenant_member(self, *, user_id: str, tenant_id: str) -> bool:
        """Return True when the user has an active membership in the tenant."""
