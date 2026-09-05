"""Ports for author-pipeline job-row progress (Slice 1 / JB-003, JB-015)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AiGenerationJobSnapshot:
    """Privileged row read: status plus optional result_ref (no HTTP)."""

    status: str
    result_ref: dict[str, Any] | None = None


class AiGenerationJobProgressPort(ABC):
    """Write status/phase on ``public.ai_generation_jobs`` (service-role RPC)."""

    @abstractmethod
    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        """Return the job row, or ``None`` if it does not exist."""

    @abstractmethod
    async def update(
        self,
        *,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error: str | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        """Apply a partial update. Omitted fields leave the current row values."""
