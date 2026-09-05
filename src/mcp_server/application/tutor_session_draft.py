"""Throttle and fail-open helper for tutor session draft patches.

Flush when **100ms** have elapsed since the last successful flush **or** the
accumulated draft grew by **32 characters** (N in the 24–40 product window).
The first token always flushes (last-flush clock starts at 0). Callers should
force-flush after the last chunk so the trailing tail is visible.
"""

from __future__ import annotations

import logging
import time

from mcp_server.domain.tutor_session_draft import TutorSessionDraftPort

logger = logging.getLogger(__name__)

DRAFT_PATCH_MIN_INTERVAL_SECONDS = 0.1
DRAFT_PATCH_EVERY_N_CHARS = 32


class DraftPatchThrottle:
    """Decide when a growing draft should be written."""

    def __init__(self) -> None:
        self._last_monotonic = 0.0
        self._last_len = 0

    def should_flush(self, text: str, *, force: bool = False) -> bool:
        if force:
            return True
        now = time.monotonic()
        if (now - self._last_monotonic) >= DRAFT_PATCH_MIN_INTERVAL_SECONDS:
            return True
        if (len(text) - self._last_len) >= DRAFT_PATCH_EVERY_N_CHARS:
            return True
        return False

    def mark_flushed(self, text: str) -> None:
        self._last_monotonic = time.monotonic()
        self._last_len = len(text)


async def patch_tutor_session_draft_fail_open(
    port: TutorSessionDraftPort | None,
    *,
    session_id: str,
    draft_reply: str | None,
) -> None:
    """Call the draft port. Fail-open: log and continue on write errors."""
    if port is None:
        return
    try:
        await port.patch(session_id=session_id, draft_reply=draft_reply)
    except Exception:
        logger.warning("tutor session draft patch failed")
