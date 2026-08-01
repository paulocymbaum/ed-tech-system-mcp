"""Tests for status logs, state machine, and status page contracts."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.status.build_manifest import build_manifest  # noqa: E402
from scripts.status.models import (  # noqa: E402
    INCIDENT_TYPES,
    IncidentState,
    StatusLogRecord,
    CoverageSnapshot,
    build_filename,
    transition_state,
)
from scripts.status.prune_logs import FILENAME_PATTERN, prune_status_logs  # noqa: E402
from scripts.status.record_incident import record_incident, record_snapshot  # noqa: E402


def test_pareto_incident_types_are_five() -> None:
    assert len(INCIDENT_TYPES) == 5
    assert "securityGateFailure" in INCIDENT_TYPES
    assert "dependencyUnavailable" in INCIDENT_TYPES


def test_state_machine_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError, match="Invalid transition"):
        transition_state(IncidentState.RESOLVED, IncidentState.OPEN)


def test_incident_filename_uses_camel_case_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.status.record_incident.STATUS_LOGS_DIR", tmp_path)
    path = record_incident("deployFailure", summary="Vercel deploy failed")
    assert path.name.startswith("incident-")
    assert path.name.endswith("-deployFailure.json")
    assert FILENAME_PATTERN.match(path.name)


def test_snapshot_record_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.status.record_incident.STATUS_LOGS_DIR", tmp_path)
    path = record_snapshot(
        coverage=CoverageSnapshot(percent=88.5, passed=10, failed=0, skipped=1),
        summary="verify passed",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["recordKind"] == "snapshot"
    assert payload["testCoverage"]["percent"] == 88.5


def test_prune_removes_files_older_than_twelve_months(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.status.prune_logs.STATUS_LOGS_DIR", tmp_path)
    old_ts = datetime.now(tz=UTC) - timedelta(days=400)
    old_name = build_filename(
        StatusLogRecord(
            recordKind="incident",
            id="incident-old-securityGateFailure",
            incidentType="securityGateFailure",
            layer="ci",
            component="safetyPipeline",
            state=IncidentState.OPEN,
            severity="critical",
            title="old",
            timestamp=old_ts,
        ),
    )
    (tmp_path / old_name).write_text("{}", encoding="utf-8")
    fresh_name = build_filename(
        StatusLogRecord(
            recordKind="snapshot",
            id="snapshot-new-testCoverage",
            layer="ci",
            component="verifyPipeline",
            state="operational",
            severity="low",
            title="new",
            timestamp=datetime.now(tz=UTC),
        ),
    )
    (tmp_path / fresh_name).write_text("{}", encoding="utf-8")

    removed = prune_status_logs()
    assert len(removed) == 1
    assert not (tmp_path / old_name).exists()
    assert (tmp_path / fresh_name).exists()


def test_status_page_assets_exist() -> None:
    assert (REPO_ROOT / "public/status/index.html").is_file()
    assert (REPO_ROOT / "public/status/status.css").is_file()
    assert (REPO_ROOT / "public/status/status.js").is_file()


def test_build_manifest_has_layer_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    logs = tmp_path / "status-logs"
    logs.mkdir()
    monkeypatch.setattr("scripts.status.record_incident.STATUS_LOGS_DIR", logs)
    monkeypatch.setattr("scripts.status.build_manifest.STATUS_LOGS_DIR", logs)
    monkeypatch.setattr(
        "scripts.status.build_manifest.MANIFEST_PATH",
        tmp_path / "manifest.json",
    )
    record_incident("qualityGateFailure", summary="pytest failed")
    manifest = build_manifest()
    assert manifest["overallState"] in {
        "operational",
        "degraded",
        "partialOutage",
        "majorOutage",
    }
    assert "ci" in manifest["historyByLayer"]
