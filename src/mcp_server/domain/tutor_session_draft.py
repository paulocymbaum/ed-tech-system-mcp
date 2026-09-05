"""Port for privileged tutor-session draft_reply patches (JB-012)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TutorSessionDraftPort(ABC):
    """Write ``learner.tutor_sessions.draft_reply`` via service-only RPC."""

    @abstractmethod
    async def patch(self, *, session_id: str, draft_reply: str | None) -> None:
        """Set or clear the session draft. ``None`` clears the column."""
