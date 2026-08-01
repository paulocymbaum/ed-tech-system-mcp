#!/usr/bin/env python3
"""Delete status-log JSON files older than 12 months."""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_LOGS_DIR = REPO_ROOT / "status-logs"
RETENTION_MONTHS = 12

FILENAME_PATTERN = re.compile(
    r"^(?:incident|snapshot)-(\d{8}T\d{6}Z)-[a-zA-Z0-9]+\.json$",
)


def _parse_timestamp(slug: str) -> datetime:
    normalized = slug.removesuffix("Z")
    return datetime.strptime(normalized, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)


def _cutoff() -> datetime:
    now = datetime.now(tz=UTC)
    year = now.year
    month = now.month - RETENTION_MONTHS
    while month <= 0:
        month += 12
        year -= 1
    return now.replace(year=year, month=month, day=min(now.day, 28))


def prune_status_logs() -> list[Path]:
    if not STATUS_LOGS_DIR.is_dir():
        return []

    removed: list[Path] = []
    cutoff = _cutoff()
    for path in sorted(STATUS_LOGS_DIR.glob("*.json")):
        match = FILENAME_PATTERN.match(path.name)
        if match is None:
            continue
        if _parse_timestamp(match.group(1)) < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def main() -> int:
    removed = prune_status_logs()
    for path in removed:
        print(f"removed {path.relative_to(REPO_ROOT)}")
    print(f"pruned {len(removed)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
