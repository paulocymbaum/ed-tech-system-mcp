"""Domain ports and types for LLM routing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum

TOKEN_LIMIT_DEACTIVATION_HOURS = 3
VALID_GROQ_COMPLEXITY_TIERS: frozenset[int] = frozenset({1, 2, 3})

DEVELOPER_PLAN_GROQ_MODEL_IDS: frozenset[str] = frozenset(
    {
        # Legacy ids kept for registry/history; Groq may retire them.
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        # Current Groq developer-plan chat models (2026-08).
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "groq/compound",
        "groq/compound-mini",
    }
)


class LLMComplexity(IntEnum):
    """Requested reasoning depth for model selection."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass(frozen=True)
class GroqActiveModel:
    """Active model from Supabase ``list_active_groq_models``."""

    model_id: str
    complexity: frozenset[int]


@dataclass(frozen=True)
class GroqModelRecord:
    """Registry view of a Groq model and its routing availability."""

    model_id: str
    display_name: str
    active: bool
    is_free: bool
    is_developer_plan: bool
    is_routable: bool
    deactivated_until: datetime | None = None
    complexity: frozenset[int] = frozenset({2})


def normalize_complexity_tiers(raw: object) -> frozenset[int] | None:
    """Parse and validate a complexity array from the backend list contract."""
    if not isinstance(raw, list) or not raw:
        return None
    tiers: set[int] = set()
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, int):
            return None
        if item not in VALID_GROQ_COMPLEXITY_TIERS:
            return None
        tiers.add(item)
    if not tiers:
        return None
    return frozenset(tiers)


def is_developer_plan_groq_model(model_id: str) -> bool:
    """Return whether a model id is included on the Groq developer plan."""
    return model_id in DEVELOPER_PLAN_GROQ_MODEL_IDS


class IGroqActiveModelListClient(ABC):
    """Port for the backend active Groq model allowlist."""

    @abstractmethod
    def fetch_active_models(self) -> list[GroqActiveModel]:
        """Return active models with operator-configured complexity tiers."""


class IGroqModelRegistry(ABC):
    """Port for dynamic Groq model availability."""

    @abstractmethod
    def refresh_active_models(self) -> None:
        """Reload registry entries from the active-model list client."""

    @abstractmethod
    def refresh_from_catalog(self) -> None:
        """Compatibility alias for ``refresh_active_models``."""

    @abstractmethod
    def list_records(self) -> list[GroqModelRecord]:
        """Return all known models (active and inactive)."""

    @abstractmethod
    def get_active_model_ids(self) -> list[str]:
        """Return model ids currently eligible for routing (any complexity)."""

    @abstractmethod
    def get_active_model_ids_for_complexity(self, complexity: LLMComplexity) -> list[str]:
        """Return active model ids that support the requested complexity tier."""

    @abstractmethod
    def deactivate_until(self, model_id: str, until: datetime) -> None:
        """Mark a model inactive until the given timestamp."""

    @abstractmethod
    def is_known_model(self, model_id: str) -> bool:
        """Return whether the model id exists in the registry."""


class ILLMDebounceGate(ABC):
    """Port that spaces outbound LLM provider calls per complexity tier."""

    @abstractmethod
    def acquire_sync(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        """Block until a new provider call is allowed for this complexity (sync)."""

    @abstractmethod
    async def acquire(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        """Wait until a new provider call is allowed for this complexity (async)."""


def token_limit_deactivation_until(*, now: datetime | None = None) -> datetime:
    """Return the deactivation deadline for token-limit errors."""
    current = now or datetime.now(tz=UTC)
    return current + timedelta(hours=TOKEN_LIMIT_DEACTIVATION_HOURS)
