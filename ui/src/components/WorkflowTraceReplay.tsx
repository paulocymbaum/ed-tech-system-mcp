import { useEffect, useMemo, useState } from "react";

import type { WorkflowTraceStep } from "../api/workflows";

type WorkflowTraceReplayProps = {
  trace: WorkflowTraceStep[];
  onActiveStepChange: (step: WorkflowTraceStep | null, attempts: Record<string, number>) => void;
};

function formatRetryCounts(retryCounts: Record<string, number>) {
  const entries = Object.entries(retryCounts);
  if (entries.length === 0) {
    return null;
  }
  return entries.map(([key, value]) => `${key.replace(/_count$/, "")}: ${value}`).join(" · ");
}

export function WorkflowTraceReplay({ trace, onActiveStepChange }: WorkflowTraceReplayProps) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);

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
        {trace.map((step) => {
          const isActive = activeStep?.step === step.step;
          const retrySummary = formatRetryCounts(step.retry_counts);
          return (
            <li
              key={`${step.step}-${step.node_id}-${step.attempt}`}
              className={`trace-item ${isActive ? "active" : ""} status-${step.status}`}
            >
              <button
                type="button"
                className="trace-item-button"
                onClick={() => {
                  setPlaying(false);
                  setCursor(step.step);
                }}
              >
                <span className="trace-item-title">
                  #{step.step} {step.node_id.replaceAll("_", " ")}
                  {step.attempt > 1 ? ` (attempt ${step.attempt})` : ""}
                </span>
                <span className={`trace-status trace-status-${step.status}`}>{step.status}</span>
                {retrySummary && <span className="trace-meta">retries · {retrySummary}</span>}
                {step.validation_errors.length > 0 && (
                  <span className="trace-errors">{step.validation_errors.join(" · ")}</span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
