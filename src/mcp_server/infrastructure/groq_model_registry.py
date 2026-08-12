"""In-memory Groq model registry with timed deactivation."""

from __future__ import annotations

from datetime import UTC, datetime

from mcp_server.domain.llm_routing import (
    GroqActiveModel,
    GroqModelRecord,
    IGroqActiveModelListClient,
    IGroqModelRegistry,
    LLMComplexity,
)


class GroqModelRegistry(IGroqModelRegistry):
    """Process-local registry backed by Supabase active Groq models."""

    def __init__(self, list_client: IGroqActiveModelListClient) -> None:
        self._list_client = list_client
        self._records: dict[str, GroqModelRecord] = {}

    def refresh_active_models(self) -> None:
        models = self._list_client.fetch_active_models()
        now = datetime.now(tz=UTC)
        refreshed: dict[str, GroqModelRecord] = {}
        for model in models:
            existing = self._records.get(model.model_id)
            refreshed[model.model_id] = _record_from_active_model(
                model,
                now=now,
                deactivated_until=existing.deactivated_until if existing else None,
            )
        self._records = refreshed

    def refresh_from_catalog(self) -> None:
        self.refresh_active_models()

    def list_records(self) -> list[GroqModelRecord]:
        self._expire_deactivations()
        return list(self._records.values())

    def get_active_model_ids(self) -> list[str]:
        self._expire_deactivations()
        return sorted(
            record.model_id
            for record in self._records.values()
            if record.active and record.is_routable
        )

    def get_active_model_ids_for_complexity(self, complexity: LLMComplexity) -> list[str]:
        self._expire_deactivations()
        tier = int(complexity)
        return sorted(
            record.model_id
            for record in self._records.values()
            if record.active and record.is_routable and tier in record.complexity
        )

    def deactivate_until(self, model_id: str, until: datetime) -> None:
        self._expire_deactivations()
        existing = self._records.get(model_id)
        if existing is None:
            return
        self._records[model_id] = GroqModelRecord(
            model_id=model_id,
            display_name=existing.display_name,
            active=False,
            is_free=existing.is_free,
            is_developer_plan=existing.is_developer_plan,
            is_routable=existing.is_routable,
            deactivated_until=until,
            complexity=existing.complexity,
        )

    def is_known_model(self, model_id: str) -> bool:
        self._expire_deactivations()
        return model_id in self._records

    def _expire_deactivations(self) -> None:
        now = datetime.now(tz=UTC)
        for model_id, record in list(self._records.items()):
            if record.deactivated_until is None:
                continue
            if record.deactivated_until <= now:
                self._records[model_id] = GroqModelRecord(
                    model_id=record.model_id,
                    display_name=record.display_name,
                    active=True,
                    is_free=record.is_free,
                    is_developer_plan=record.is_developer_plan,
                    is_routable=record.is_routable,
                    deactivated_until=None,
                    complexity=record.complexity,
                )


def _record_from_active_model(
    model: GroqActiveModel,
    *,
    now: datetime,
    deactivated_until: datetime | None,
) -> GroqModelRecord:
    is_deactivated = deactivated_until is not None and deactivated_until > now
    return GroqModelRecord(
        model_id=model.model_id,
        display_name=model.model_id,
        active=not is_deactivated,
        is_free=True,
        is_developer_plan=False,
        is_routable=True,
        deactivated_until=deactivated_until if is_deactivated else None,
        complexity=model.complexity,
    )
