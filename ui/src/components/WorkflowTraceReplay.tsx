import { useEffect, useMemo, useState } from "react";

import type { WorkflowTraceStep } from "../api/workflows";
import { buildTraceSections, initialCollapsedGroups } from "../lib/ragNodeGroups";

type WorkflowTraceReplayProps = {
  trace: WorkflowTraceStep[];
  nodeGroups?: import("../api/workflows").NodeGroup[];
  onActiveStepChange: (step: WorkflowTraceStep | null, attempts: Record<string, number>) => void;
};

function formatRetryCounts(retryCounts: Record<string, number>) {
  const entries = Object.entries(retryCounts);
  if (entries.length === 0) {
    return null;
  }
  return entries.map(([key, value]) => `${key.replace(/_count$/, "")}: ${value}`).join(" · ");
}

function nextNodeId(trace: WorkflowTraceStep[], index: number): string | null {
  return trace[index + 1]?.node_id ?? null;
}

function TraceStepItem({
  step,
  trace,
  index,
  isActive,
  onSelect,
}: {
  step: WorkflowTraceStep;
  trace: WorkflowTraceStep[];
  index: number;
  isActive: boolean;
  onSelect: (stepNumber: number) => void;
}) {
  const retrySummary = formatRetryCounts(step.retry_counts);
  const routeTarget = step.status === "retry" ? nextNodeId(trace, index) : null;

  return (
    <li
      className={`trace-item ${isActive ? "active" : ""} trace-item--${step.status} trace-item--nested`}
    >
      <button
        type="button"
        className="trace-item-button"
        onClick={() => onSelect(step.step)}
      >
        <span className="trace-item-title">
          #{step.step} {step.node_id.replaceAll("_", " ")}
          {step.attempt > 1 ? ` (attempt ${step.attempt})` : ""}
        </span>
        <span className={`trace-status trace-status-${step.status}`}>{step.status}</span>
        {routeTarget && (
          <span className="trace-route">retry route → {routeTarget.replaceAll("_", " ")}</span>
        )}
        {retrySummary && <span className="trace-meta">retries · {retrySummary}</span>}
        {step.validation_errors.length > 0 && (
          <span className="trace-errors">{step.validation_errors.join(" · ")}</span>
        )}
      </button>
    </li>
  );
}

export function WorkflowTraceReplay({
  trace,
  nodeGroups = [],
  onActiveStepChange,
}: WorkflowTraceReplayProps) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setCursor(trace.length);
    setPlaying(false);
    setExpandedGroups(new Set());
  }, [trace]);

  const collapsedGroups = useMemo(() => initialCollapsedGroups(nodeGroups), [nodeGroups]);

  const attempts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const step of trace.slice(0, cursor)) {
      counts[step.node_id] = step.attempt;
    }
    return counts;
  }, [trace, cursor]);

  const activeStep = cursor > 0 ? (trace[cursor - 1] ?? null) : null;

  useEffect(() => {
    onActiveStepChange(activeStep, attempts);
  }, [activeStep, attempts, onActiveStepChange]);

  useEffect(() => {
    if (!playing || cursor >= trace.length) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setCursor((value) => value + 1);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [playing, cursor, trace.length]);

  const sections = useMemo(() => buildTraceSections(trace, nodeGroups), [trace, nodeGroups]);

  if (trace.length === 0) {
    return (
      <div className="trace-panel">
        <h3>Execution replay</h3>
        <p className="muted">Run the workflow to record node-by-node execution, retries, and failures.</p>
      </div>
    );
  }

  return (
    <div className="trace-panel">
      <div className="trace-header">
        <h3>Execution replay</h3>
        <div className="trace-controls">
          <button type="button" onClick={() => setCursor(0)}>
            Reset
          </button>
          <button
            type="button"
            onClick={() => {
              setPlaying(false);
              setCursor((value) => Math.max(0, value - 1));
            }}
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => {
              setPlaying(false);
              setCursor((value) => Math.min(trace.length, value + 1));
            }}
          >
            Next
          </button>
          <button type="button" onClick={() => setPlaying((value) => !value)}>
            {playing ? "Pause" : "Play"}
          </button>
        </div>
      </div>

      <p className="trace-progress">
        Step {cursor} / {trace.length}
      </p>

      <ol className="trace-list">
        {sections.map((section) => {
          if (section.type === "step") {
            const { step, index } = section;
            return (
              <TraceStepItem
                key={`${step.step}-${step.node_id}-${step.attempt}`}
                step={step}
                trace={trace}
                index={index}
                isActive={activeStep?.step === step.step}
                onSelect={(stepNumber) => {
                  setPlaying(false);
                  setCursor(stepNumber);
                }}
              />
            );
          }

          const isExpanded = expandedGroups.has(section.group.id);
          const isCollapsedByDefault = collapsedGroups.has(section.group.id);
          const showChildren = isExpanded || !isCollapsedByDefault;
          const groupHasActive = section.steps.some(({ step }) => activeStep?.step === step.step);

          return (
            <li
              key={`group-${section.group.id}`}
              className={`trace-group ${groupHasActive ? "active" : ""}`}
            >
              <button
                type="button"
                className="trace-group-toggle"
                onClick={() => {
                  setExpandedGroups((current) => {
                    const next = new Set(current);
                    if (next.has(section.group.id)) {
                      next.delete(section.group.id);
                    } else {
                      next.add(section.group.id);
                    }
                    return next;
                  });
                }}
              >
                <span className="trace-group-chevron">{showChildren ? "▾" : "▸"}</span>
                <span className="trace-group-title">{section.group.label}</span>
                <span className="trace-meta">{section.steps.length} substeps</span>
              </button>
              {showChildren && (
                <ol className="trace-list trace-list--nested">
                  {section.steps.map(({ step, index }) => (
                    <TraceStepItem
                      key={`${step.step}-${step.node_id}-${step.attempt}`}
                      step={step}
                      trace={trace}
                      index={index}
                      isActive={activeStep?.step === step.step}
                      onSelect={(stepNumber) => {
                        setPlaying(false);
                        setCursor(stepNumber);
                      }}
                    />
                  ))}
                </ol>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
