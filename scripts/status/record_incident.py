#!/usr/bin/env python3
"""Record status-log incidents and snapshots (Pareto types only)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.status.models import (  # noqa: E402
    INCIDENT_TYPES,
    IncidentState,
    StateTransition,
    StatusLogRecord,
    CoverageSnapshot,
    build_filename,
    format_timestamp_slug,
    incident_meta,
    utc_now,
)

STATUS_LOGS_DIR = REPO_ROOT / "status-logs"


def _load_coverage(path: Path, *, passed: int, failed: int, skipped: int) -> CoverageSnapshot:
    percent: float | None = None
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw = payload.get("totals", {}).get("percent_covered")
        if raw is not None:
            percent = float(raw)
    return CoverageSnapshot(
        percent=percent,
        passed=passed,
        failed=failed,
        skipped=skipped,
    )


def _write_record(record: StatusLogRecord) -> Path:
    STATUS_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATUS_LOGS_DIR / build_filename(record)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def record_incident(
    incident_type: str,
    *,
    summary: str,
    state: IncidentState = IncidentState.OPEN,
    source: str = "github-actions",
    run_id: str | None = None,
    git_ref: str | None = None,
    git_sha: str | None = None,
    coverage: CoverageSnapshot | None = None,
) -> Path:
    meta = incident_meta(incident_type)
    now = utc_now()
    record_id = f"incident-{format_timestamp_slug(now)}-{incident_type}"
    record = StatusLogRecord(
        recordKind="incident",
        id=record_id,
        incidentType=incident_type,
        layer=meta["layer"],
        component=meta["component"],
        state=state,
        severity=meta["severity"],  # type: ignore[arg-type]
        title=meta["title"],
        summary=summary,
        source=source,
        runId=run_id,
        gitRef=git_ref,
        gitSha=git_sha,
        timestamp=now,
        testCoverage=coverage,
        transitions=[
            StateTransition(
                fromState=IncidentState.DETECTED,
                toState=state,
                at=now,
            ),
        ],
    )
    return _write_record(record)


def record_snapshot(
    *,
    coverage: CoverageSnapshot,
    summary: str = "CI verify passed",
    run_id: str | None = None,
    git_ref: str | None = None,
    git_sha: str | None = None,
) -> Path:
    now = utc_now()
    record_id = f"snapshot-{format_timestamp_slug(now)}-testCoverage"
    record = StatusLogRecord(
        recordKind="snapshot",
        id=record_id,
        layer="ci",
        component="verifyPipeline",
        state="operational",
        severity="low",
        title="Test coverage snapshot",
        summary=summary,
        runId=run_id,
        gitRef=git_ref,
        gitSha=git_sha,
        timestamp=now,
        testCoverage=coverage,
    )
    return _write_record(record)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a status-log incident or snapshot.")
    sub = parser.add_subparsers(dest="command", required=True)

    incident_parser = sub.add_parser("incident")
    incident_parser.add_argument(
        "incident_type",
        choices=sorted(INCIDENT_TYPES),
    )
    incident_parser.add_argument("--summary", required=True)
    incident_parser.add_argument("--state", default=IncidentState.OPEN.value)
    incident_parser.add_argument("--coverage-file", type=Path)

    snapshot_parser = sub.add_parser("snapshot")
    snapshot_parser.add_argument("--coverage-file", type=Path, required=True)
    snapshot_parser.add_argument("--summary", default="CI verify passed")

    snapshot_parser.add_argument("--passed", type=int, default=0)
    snapshot_parser.add_argument("--failed", type=int, default=0)
    snapshot_parser.add_argument("--skipped", type=int, default=0)

    for sub_parser in (incident_parser, snapshot_parser):
        sub_parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID"))
        sub_parser.add_argument("--git-ref", default=os.getenv("GITHUB_REF"))
        sub_parser.add_argument("--git-sha", default=os.getenv("GITHUB_SHA"))

    args = parser.parse_args()
    coverage = None
    if args.command == "incident":
        if getattr(args, "coverage_file", None) and args.coverage_file:
            coverage = _load_coverage(
                args.coverage_file,
                passed=getattr(args, "passed", 0),
                failed=getattr(args, "failed", 0),
                skipped=getattr(args, "skipped", 0),
            )
    else:
        coverage = _load_coverage(
            args.coverage_file,
            passed=args.passed,
            failed=args.failed,
            skipped=args.skipped,
        )

    if args.command == "incident":
        path = record_incident(
            args.incident_type,
            summary=args.summary,
            state=IncidentState(args.state),
            run_id=args.run_id,
            git_ref=args.git_ref,
            git_sha=args.git_sha,
            coverage=coverage,
        )
    else:
        if coverage is None:
            print("ERROR: --coverage-file required for snapshot", file=sys.stderr)
            return 1
        path = record_snapshot(
            coverage=coverage,
            summary=args.summary,
            run_id=args.run_id,
            git_ref=args.git_ref,
            git_sha=args.git_sha,
        )

    print(path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
