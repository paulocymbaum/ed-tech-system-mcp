"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base class for domain-layer errors."""


class ResourceNotFoundError(DomainError):
    """Raised when a requested resource does not exist or is not configured."""


class DomainValidationError(DomainError):
    """Raised when domain invariants are violated.

    Named ``DomainValidationError`` to avoid collision with Pydantic and FastMCP
    ``ValidationError`` types at the interface boundary.
    """


class ExternalRateLimitError(DomainError):
    """Raised when outbound external API calls exceed the configured per-minute cap."""


class ExternalServiceError(DomainError):
    """Raised when an outbound model or API call fails closed to the caller."""


class DomainAuthorizationError(DomainError):
    """Raised when a caller is missing or not allowed to invoke a privileged tool."""
