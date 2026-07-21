"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base class for domain-layer errors."""


class ResourceNotFoundError(DomainError):
    """Raised when a requested resource does not exist."""


class ValidationError(DomainError):
    """Raised when domain invariants are violated."""
