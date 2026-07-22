"""Domain exception hierarchy and invariant tests (T07+)."""

import pytest

from mcp_server.domain.exceptions import (
    DomainError,
    DomainValidationError,
    ResourceNotFoundError,
)
from mcp_server.domain.invariants import (
    require_credential,
    require_non_empty_text,
    require_positive_int,
)


def test_t07_domain_exception_hierarchy() -> None:
    assert isinstance(ResourceNotFoundError(), DomainError)
    assert isinstance(DomainValidationError(), DomainError)


def test_t07b_domain_exceptions_preserve_message() -> None:
    not_found = ResourceNotFoundError("document missing")
    validation = DomainValidationError("query must not be empty")

    assert str(not_found) == "document missing"
    assert str(validation) == "query must not be empty"


def test_t07c_resource_not_found_raise_and_catch() -> None:
    with pytest.raises(ResourceNotFoundError, match="missing credentials"):
        raise ResourceNotFoundError("missing credentials")


def test_t07d_domain_validation_raise_and_catch() -> None:
    with pytest.raises(DomainValidationError, match="must not be empty"):
        raise DomainValidationError("query must not be empty")


def test_t07e_require_non_empty_text_rejects_blank() -> None:
    with pytest.raises(DomainValidationError, match="query must not be empty"):
        require_non_empty_text("   ", field="query")


def test_t07f_require_non_empty_text_returns_stripped_value() -> None:
    assert require_non_empty_text("  plants  ", field="query") == "plants"


def test_t07g_require_positive_int_rejects_non_positive() -> None:
    with pytest.raises(DomainValidationError, match="limit must be positive"):
        require_positive_int(0, field="limit")


def test_t07h_require_credential_raises_resource_not_found() -> None:
    with pytest.raises(ResourceNotFoundError, match="YouTube API credentials"):
        require_credential("", resource="YouTube API")
