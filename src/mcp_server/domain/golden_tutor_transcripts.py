"""Sample Socratic transcripts for turn-1 policy audit (E18.2)."""

from __future__ import annotations

from typing import NamedTuple

from mcp_server.domain.socratic import validate_socratic_reply


class TutorTranscriptSample(NamedTuple):
    sample_id: str
    turn_index: int
    asked_full_solution: bool
    reply: str
    expect_ok: bool


_DUMP = (
    "Here is the full function:\n"
    "```javascript\n"
    "function parseAge(raw) {\n"
    "  const n = Number(raw);\n"
    "  if (!Number.isFinite(n) || n < 0) return null;\n"
    "  return Math.trunc(n);\n"
    "}\n"
    "```\n"
)

_HINT = (
    "You're close on Number(raw).\n"
    "What happens if the text is not a finite number?\n"
)


def load_tutor_transcript_samples() -> tuple[TutorTranscriptSample, ...]:
    return (
        TutorTranscriptSample("good-turn1", 1, False, _HINT, True),
        TutorTranscriptSample("dump-turn1", 1, False, _DUMP, False),
        TutorTranscriptSample("dump-asked-full", 1, True, _DUMP, True),
        TutorTranscriptSample(
            "tiny-hint-fence",
            1,
            False,
            "Try `Number.isFinite`.\nWhat does it return for NaN?\n",
            True,
        ),
    )


class TranscriptAuditMismatch(NamedTuple):
    sample_id: str
    expected_ok: bool
    actual_ok: bool
    errors: list[str]


def audit_tutor_transcripts(
    samples: tuple[TutorTranscriptSample, ...] | None = None,
) -> list[TranscriptAuditMismatch]:
    """Return mismatches; empty list means the policy audit passed."""
    rows = samples if samples is not None else load_tutor_transcript_samples()
    mismatches: list[TranscriptAuditMismatch] = []
    for sample in rows:
        check = validate_socratic_reply(
            sample.reply,
            asked_full_solution=sample.asked_full_solution,
            turn_index=sample.turn_index,
        )
        actual = bool(check["ok"])
        if actual != sample.expect_ok:
            mismatches.append(
                TranscriptAuditMismatch(
                    sample_id=sample.sample_id,
                    expected_ok=sample.expect_ok,
                    actual_ok=actual,
                    errors=list(check["errors"]),
                )
            )
    return mismatches
