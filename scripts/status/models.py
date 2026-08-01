"""Pareto incident taxonomy and state machine for status logs (scripts-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1
RETENTION_MONTHS = 12

# Pareto 20% — five incident types cover ~80% of operational pain.
INCIDENT_TYPES: dict[str, dict[str, str]] = {
    "securityGateFailure": {
        "layer": "ci",
        "component": "safetyPipeline",
        "severity": "critical",
        "title": "Security gate failed",
    },
    "qualityGateFailure": {
        "layer": "ci",
        "component": "verifyPipeline",
        "severity": "high",
        "title": "Quality gate failed",
    },
    "deployFailure": {
        "layer": "deploy",
        "component": "vercelMcp",
        "severity": "critical",
        "title": "Production deploy failed",
    },
    "availabilityLoss": {
        "layer": "interface",
        "component": "mcpHttp",
        "severity": "critical",
        "title": "MCP availability loss",
    },
    "dependencyUnavailable": {
        "layer": "infrastructure",
        "component": "externalIntegration",
        "severity": "high",
        "title": "External dependency unavailable",
    },
}


class IncidentState(StrEnum):
    DETECTED = "detected"
    OPEN = "open"
    INVESTIGATING = "investigating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    RISK = "risk"


class ComponentHealth(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partialOutage"
    MAJOR_OUTAGE = "majorOutage"
    UNKNOWN = "unknown"


ALLOWED_INCIDENT_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.DETECTED: {IncidentState.OPEN, IncidentState.RISK},
    IncidentState.OPEN: {IncidentState.INVESTIGATING, IncidentState.RESOLVED},
    IncidentState.INVESTIGATING: {IncidentState.MONITORING, IncidentState.RESOLVED},
    IncidentState.MONITORING: {IncidentState.RESOLVED, IncidentState.OPEN},
    IncidentState.RISK: {IncidentState.MONITORING, IncidentState.RESOLVED, IncidentState.OPEN},
    IncidentState.RESOLVED: set(),
}


class StateTransition(BaseModel):
    fromState: IncidentState
    toState: IncidentState
    at: datetime


class CoverageSnapshot(BaseModel):
    percent: float | None = None
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class StatusLogRecord(BaseModel):
    """Incident or snapshot written under status-logs/."""

    schemaVersion: int = SCHEMA_VERSION
    recordKind: Literal["incident", "snapshot"]
    id: str
    incidentType: str | None = None
    layer: str
    component: str
    state: IncidentState | Literal["operational"] = IncidentState.OPEN
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    title: str
    summary: str = ""
    source: str = "github-actions"
    runId: str | None = None
    gitRef: str | None = None
    gitSha: str | None = None
    timestamp: datetime
    resolvedAt: datetime | None = None
    testCoverage: CoverageSnapshot | None = None
    transitions: list[StateTransition] = Field(default_factory=list)

    @field_validator("incidentType")
    @classmethod
    def validate_incident_type(cls, value: str | None, info: Any) -> str | None:
        if info.data.get("recordKind") == "incident" and value not in INCIDENT_TYPES:
            msg = f"Unknown incidentType: {value}"
            raise ValueError(msg)
        return value


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def format_timestamp_slug(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_filename(record: StatusLogRecord) -> str:
    slug = record.incidentType or "testCoverage"
    prefix = "incident" if record.recordKind == "incident" else "snapshot"
    return f"{prefix}-{format_timestamp_slug(record.timestamp)}-{slug}.json"


def transition_state(
    current: IncidentState,
    target: IncidentState,
    *,
    at: datetime | None = None,
) -> tuple[IncidentState, StateTransition]:
    allowed = ALLOWED_INCIDENT_TRANSITIONS.get(current, set())
    if target not in allowed and current != target:
        msg = f"Invalid transition {current.value} -> {target.value}"
        raise ValueError(msg)
    when = at or utc_now()
    return target, StateTransition(fromState=current, toState=target, at=when)


def incident_meta(incident_type: str) -> dict[str, str]:
    meta = INCIDENT_TYPES.get(incident_type)
    if meta is None:
        msg = f"Unknown incident type: {incident_type}"
        raise KeyError(msg)
    return meta
