"""In-memory Groq model registry with timed deactivation."""

from __future__ import annotations

from datetime import UTC, datetime

from mcp_server.domain.llm_routing import (
    GroqModelCatalogEntry,
    GroqModelRecord,
    IGroqModelCatalogClient,
    IGroqModelRegistry,
    is_developer_plan_groq_model,
    is_free_groq_model_pricing,
    is_plan_accessible_groq_model,
    is_routable_groq_chat_model,
)


class GroqModelRegistry(IGroqModelRegistry):
    """Process-local registry backed by the live Groq catalog."""

    def __init__(self, catalog_client: IGroqModelCatalogClient) -> None:
        self._catalog_client = catalog_client
        self._records: dict[str, GroqModelRecord] = {}

    def refresh_from_catalog(self) -> None:
        catalog_entries = self._catalog_client.fetch_models()
        now = datetime.now(tz=UTC)
        refreshed: dict[str, GroqModelRecord] = {}
        for entry in catalog_entries:
            existing = self._records.get(entry.model_id)
            refreshed[entry.model_id] = _record_from_catalog_entry(
                entry,
                now=now,
                deactivated_until=existing.deactivated_until if existing else None,
            )
        self._records = refreshed

    def list_records(self) -> list[GroqModelRecord]:
        self._expire_deactivations()
        return list(self._records.values())

    def get_active_model_ids(self) -> list[str]:
        self._expire_deactivations()
        return [
            record.model_id
            for record in self._records.values()
            if record.active and record.is_routable
        ]

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
                    active=_default_active(record),
                    is_free=record.is_free,
                    is_developer_plan=record.is_developer_plan,
                    is_routable=record.is_routable,
                    deactivated_until=None,
                )


def _default_active(record: GroqModelRecord) -> bool:
    return (record.is_free or record.is_developer_plan) and record.is_routable


def _record_from_catalog_entry(
    entry: GroqModelCatalogEntry,
    *,
    now: datetime,
    deactivated_until: datetime | None,
) -> GroqModelRecord:
    is_free = is_free_groq_model_pricing(entry.pricing)
    is_developer_plan = is_developer_plan_groq_model(entry.model_id)
    is_routable = is_routable_groq_chat_model(entry)
    is_accessible = is_plan_accessible_groq_model(
        model_id=entry.model_id,
        pricing=entry.pricing,
    )
    is_deactivated = deactivated_until is not None and deactivated_until > now
    return GroqModelRecord(
        model_id=entry.model_id,
        display_name=entry.display_name,
        active=is_accessible and is_routable and not is_deactivated,
        is_free=is_free,
        is_developer_plan=is_developer_plan,
        is_routable=is_routable,
        deactivated_until=deactivated_until if is_deactivated else None,
    )
