"""Praxis v2 content-block fence validation (GA-10..13).

Lessons may embed structured v2 blocks in ``readme_markdown`` using fenced
code blocks with an ``edtech-`` info string:

    ```edtech-tip tone=tip
    **Title.** Body with `inline code`.
    ```
    ```edtech-vocabulary
    Float | 1.0 (ponto flutuante)
    Half (0.5) | 180°
    ```
    ```edtech-educator-notes
    Guidance for parents/tutors.
    ```
    ```edtech-visualizer component=fraction-pizza
    angle = (360 / denominator) * numerator
    ```

The fence travels through the existing ``readme_markdown`` transport (MCP →
``upsert_lesson_content_document`` → catalog MV ``markdown`` → FE
``MarkdownView``) — no new columns, no RPC arity change. The FE renderer
parses these fences (GA-13b binds the readout strip to the visualizer).
Unknown ``edtech-*`` fences are a validation error so typos fail loud at
authoring time instead of rendering as raw code on the student side
(fail-loud rule: no warn-and-skip over content).
"""

from __future__ import annotations

import re
from typing import Any

from mcp_server.domain.content_validators import ValidationFinding, ValidationReport

FENCE_RE = re.compile(r"^\s*```([^\n`]*)$")
KNOWN_FENCES = frozenset({"edtech-tip", "edtech-vocabulary", "edtech-educator-notes", "edtech-visualizer"})
KNOWN_VISUALIZERS = frozenset({"fraction-pizza"})
BLOCK_LINE_RE = re.compile(r"^[^|]+ \| [^|]+$")


def validate_content_blocks(readme_markdown: str) -> ValidationReport:
    """Validate every ``edtech-*`` fence in the lesson markdown."""
    report = ValidationReport()

    lines = readme_markdown.splitlines()
    open_fence: tuple[int, str, str] | None = None  # (line_no, kind, attr_string)
    body: list[str] = []

    for line_no, line in enumerate(lines, start=1):
        match = FENCE_RE.match(line)
        if match is None:
            if open_fence is not None:
                body.append(line)
            continue

        info = match.group(1).strip()
        kind, _, attrs = info.partition(" ")
        if open_fence is None:
            if not kind.startswith("edtech-"):
                continue  # ordinary fenced code (or a closing ``` with no info string)
            open_fence = (line_no, kind, attrs.strip())
            body = []
            continue

        if not kind.startswith("edtech-"):
            # Closing fence of the open block (``` / ```lang): validate and reset.
            _validate_block(report, open_fence, body)
            open_fence = None
            body = []
            continue

        # Adjacent edtech block: the previous one ended implicitly at this line.
        _validate_block(report, open_fence, body)
        open_fence = (line_no, kind, attrs.strip())
        body = []

    if open_fence is not None:
        report.findings.append(
            ValidationFinding(
                "error",
                f"edtech block opened at line {open_fence[0]} is never closed with ```",
            )
        )
    return report


def _validate_block(
    report: ValidationReport,
    open_fence: tuple[int, str, str],
    body: list[str],
) -> None:
    line_no, kind, attrs = open_fence
    where = f"edtech block at line {line_no}"
    if kind not in KNOWN_FENCES:
        report.findings.append(
            ValidationFinding("error", f"{where}: unknown block type '{kind}'")
        )
        return

    if kind == "edtech-tip":
        match = re.search(r"\btone=(tip|warning)\b", attrs)
        if match is None:
            report.findings.append(
                ValidationFinding("error", f"{where}: tone=tip|warning attribute required")
            )
        if not any(line.strip() for line in body):
            report.findings.append(ValidationFinding("error", f"{where}: body is empty"))

    elif kind == "edtech-vocabulary":
        rows = [line for line in body if line.strip()]
        if not rows:
            report.findings.append(ValidationFinding("error", f"{where}: needs term rows"))
        else:
            for row in rows:
                if not BLOCK_LINE_RE.match(row.strip()):
                    report.findings.append(
                        ValidationFinding(
                            "error", f"{where}: row '{row.strip()}' must be 'term | subtitle'"
                        )
                    )

    elif kind == "edtech-educator-notes":
        if not any(line.strip() for line in body):
            report.findings.append(ValidationFinding("error", f"{where}: body is empty"))

    elif kind == "edtech-visualizer":
        match = re.search(r"\bcomponent=([\w-]+)\b", attrs)
        if match is None:
            report.findings.append(
                ValidationFinding("error", f"{where}: component=<id> attribute required")
            )
        elif match.group(1) not in KNOWN_VISUALIZERS:
            report.findings.append(
                ValidationFinding(
                    "error",
                    f"{where}: unknown visualizer '{match.group(1)}' "
                    f"(known: {', '.join(sorted(KNOWN_VISUALIZERS))})",
                )
            )


def has_content_blocks(readme_markdown: str) -> bool:
    """True when the markdown carries at least one ``edtech-*`` fence."""
    for line in readme_markdown.splitlines():
        match = FENCE_RE.match(line)
        if match is not None and match.group(1).strip().startswith("edtech-"):
            return True
    return False


def _unused(*_args: Any) -> None:  # pragma: no cover - typing shim
    """Reserved for future block-type registry injection."""
