#!/usr/bin/env python3
"""Build public/status/manifest.json from status-logs/."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.status.models import (  # noqa: E402
    INCIDENT_TYPES,
    ComponentHealth,
    IncidentState,
    StatusLogRecord,
)

STATUS_LOGS_DIR = REPO_ROOT / "status-logs"
MANIFEST_PATH = REPO_ROOT / "public" / "status" / "manifest.json"

COMPONENTS = [
    {"id": "mcpHttp", "layer": "interface", "label": "MCP HTTP (/mcp, /health)"},
    {"id": "safetyPipeline", "layer": "ci", "label": "Safety pipeline"},
    {"id": "verifyPipeline", "layer": "ci", "label": "Tests & architecture"},
    {"id": "renderMcp", "layer": "deploy", "label": "Render MCP deploy"},
    {"id": "externalIntegration", "layer": "infrastructure", "label": "Supabase / YouTube / Groq"},
    {"id": "workflowApi", "layer": "application", "label": "Workflow API (Docker)"},
    {"id": "dockerMcp", "layer": "deploy", "label": "Docker MCP image"},
]


def _load_records() -> list[StatusLogRecord]:
    if not STATUS_LOGS_DIR.is_dir():
        return []
    records: list[StatusLogRecord] = []
    for path in sorted(STATUS_LOGS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.append(StatusLogRecord.model_validate(payload))
    records.sort(key=lambda item: item.timestamp, reverse=True)
    return records


def _component_health(records: list[StatusLogRecord], component_id: str) -> str:
    open_incidents = [
        record
        for record in records
        if record.recordKind == "incident"
        and record.component == component_id
        and record.state != IncidentState.RESOLVED
    ]
    if not open_incidents:
        return ComponentHealth.OPERATIONAL.value
    severity = open_incidents[0].severity
    if severity == "critical":
        return ComponentHealth.MAJOR_OUTAGE.value
    if severity == "high":
        return ComponentHealth.PARTIAL_OUTAGE.value
    return ComponentHealth.DEGRADED.value


def _overall_state(component_states: list[str]) -> str:
    if ComponentHealth.MAJOR_OUTAGE.value in component_states:
        return ComponentHealth.MAJOR_OUTAGE.value
    if ComponentHealth.PARTIAL_OUTAGE.value in component_states:
        return ComponentHealth.PARTIAL_OUTAGE.value
    if ComponentHealth.DEGRADED.value in component_states:
        return ComponentHealth.DEGRADED.value
    return ComponentHealth.OPERATIONAL.value


def _latest_coverage(records: list[StatusLogRecord]) -> dict[str, object] | None:
    for record in records:
        if record.testCoverage is not None:
            return record.testCoverage.model_dump()
    return None


def build_manifest() -> dict[str, object]:
    records = _load_records()
    incidents = [record for record in records if record.recordKind == "incident"]
    snapshots = [record for record in records if record.recordKind == "snapshot"]

    component_rows = []
    states: list[str] = []
    for component in COMPONENTS:
        health = _component_health(incidents, component["id"])
        states.append(health)
        last = next(
            (record for record in incidents if record.component == component["id"]),
            None,
        )
        component_rows.append(
            {
                **component,
                "health": health,
                "lastIncidentId": last.id if last else None,
            },
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(tz=UTC).isoformat(),
        "overallState": _overall_state(states),
        "paretoIncidentTypes": list(INCIDENT_TYPES.keys()),
        "testCoverage": _latest_coverage(records),
        "components": component_rows,
        "incidents": [record.model_dump(mode="json") for record in incidents[:50]],
        "snapshots": [record.model_dump(mode="json") for record in snapshots[:20]],
        "historyByLayer": _group_by_layer(incidents),
    }


def _group_by_layer(incidents: list[StatusLogRecord]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in incidents:
        grouped.setdefault(record.layer, []).append(record.model_dump(mode="json"))
    return grouped


def main() -> int:
    manifest = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(MANIFEST_PATH.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
