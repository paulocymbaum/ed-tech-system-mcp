"""Domain ports and types for LLM routing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum

TOKEN_LIMIT_DEACTIVATION_HOURS = 3
GROQ_MODEL_CATALOG_TTL_DAYS = 7
GROQ_MODEL_CATALOG_TTL_SECONDS = GROQ_MODEL_CATALOG_TTL_DAYS * 24 * 60 * 60
VALID_GROQ_COMPLEXITY_TIERS: frozenset[int] = frozenset({1, 2, 3})

DEVELOPER_PLAN_GROQ_MODEL_IDS: frozenset[str] = frozenset(
    {
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    }
)


class LLMComplexity(IntEnum):
    """Requested reasoning depth for model selection."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass(frozen=True)
class GroqModelPricing:
    """Per-token pricing returned by the Groq models API."""

    prompt: float = 0.0
    completion: float = 0.0
    request: float = 0.0
    image: float = 0.0


@dataclass(frozen=True)
class GroqModelCatalogEntry:
    """A model returned by the Groq catalog API."""

    model_id: str
    owned_by: str = ""
    display_name: str = ""
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    pricing: GroqModelPricing | None = None


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


def is_free_groq_model_pricing(pricing: GroqModelPricing | None) -> bool:
    """Return whether a Groq model is free according to catalog pricing metadata.

    Groq omits ``pricing`` on zero-cost models; those are treated as free. When
    pricing is present, every component must be zero.
    """
    if pricing is None:
        return True
    return (
        pricing.prompt == 0.0
        and pricing.completion == 0.0
        and pricing.request == 0.0
        and pricing.image == 0.0
    )


def is_developer_plan_groq_model(model_id: str) -> bool:
    """Return whether a model id is included on the Groq developer plan."""
    return model_id in DEVELOPER_PLAN_GROQ_MODEL_IDS


def is_plan_accessible_groq_model(
    *,
    model_id: str,
    pricing: GroqModelPricing | None,
) -> bool:
    """Return whether a model is eligible for routing on the free or developer plan."""
    return is_free_groq_model_pricing(pricing) or is_developer_plan_groq_model(model_id)


def is_routable_groq_chat_model(entry: GroqModelCatalogEntry) -> bool:
    """Return whether a catalog entry is eligible for chat-completion routing."""
    lowered_id = entry.model_id.lower()
    if "whisper" in lowered_id or "orpheus" in lowered_id or "prompt-guard" in lowered_id:
        return False
    if "text" not in entry.output_modalities:
        return False
    return "text" in entry.input_modalities


class IGroqModelCatalogClient(ABC):
    """Port for fetching the live Groq model catalog (ops / sync only)."""

    @abstractmethod
    def fetch_models(self) -> list[GroqModelCatalogEntry]:
        """Return models advertised by the Groq API."""


class IGroqActiveModelListClient(ABC):
    """Port for the backend active Groq model allowlist."""

    @abstractmethod
    def fetch_active_models(self) -> list[GroqActiveModel]:
        """Return active models with operator-configured complexity tiers."""


@dataclass(frozen=True)
class GroqModelCatalogSnapshot:
    """A cached Groq model catalog with fetch timestamp."""

    fetched_at: datetime
    entries: list[GroqModelCatalogEntry]


class IGroqModelCatalogCache(ABC):
    """Port for persisting Groq catalog snapshots across process restarts."""

    @abstractmethod
    def load(self) -> GroqModelCatalogSnapshot | None:
        """Return a fresh cached snapshot, or ``None`` when missing or expired."""

    @abstractmethod
    def save(self, snapshot: GroqModelCatalogSnapshot) -> None:
        """Persist a catalog snapshot."""

    @abstractmethod
    def clear(self) -> None:
        """Remove any persisted snapshot."""


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
    """Port that spaces outbound LLM provider calls."""

    @abstractmethod
    def acquire_sync(self) -> None:
        """Block until a new provider call is allowed (sync callers)."""

    @abstractmethod
    async def acquire(self) -> None:
        """Wait until a new provider call is allowed (async callers)."""


def token_limit_deactivation_until(*, now: datetime | None = None) -> datetime:
    """Return the deactivation deadline for token-limit errors."""
    current = now or datetime.now(tz=UTC)
    return current + timedelta(hours=TOKEN_LIMIT_DEACTIVATION_HOURS)
