import { useState } from "react";

import { runWorkflow, type WorkflowGraph, type WorkflowTraceStep } from "../api/workflows";

type WorkflowRunPanelProps = {
  workflow: WorkflowGraph;
  onTrace: (trace: WorkflowTraceStep[]) => void;
  onError: (message: string | null) => void;
};

export function WorkflowRunPanel({ workflow, onTrace, onError }: WorkflowRunPanelProps) {
  const [query, setQuery] = useState("fractions");
  const [topic, setTopic] = useState("fractions");
  const [gradeLevel, setGradeLevel] = useState("6th grade");
  const [running, setRunning] = useState(false);

  async function handleRun() {
    setRunning(true);
    onError(null);
    try {
      const body: Record<string, string | number> =
        workflow.id === "content-generation"
          ? { topic, grade_level: gradeLevel }
          : { query, document_limit: 5, video_limit: 2 };
      const result = await runWorkflow(workflow.id, body);
      onTrace(result.trace ?? []);
    } catch (runError) {
      onTrace([]);
      onError(runError instanceof Error ? runError.message : "Workflow run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="run-panel">
      <h3>Run workflow</h3>
      {workflow.id === "content-generation" ? (
        <div className="run-form">
          <label>
            Topic
            <input value={topic} onChange={(event) => setTopic(event.target.value)} />
          </label>
          <label>
            Grade level
            <input value={gradeLevel} onChange={(event) => setGradeLevel(event.target.value)} />
          </label>
        </div>
      ) : (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
        </div>
      )}
      <button type="button" className="run-button" disabled={running} onClick={() => void handleRun()}>
        {running ? "Running…" : "Run and capture trace"}
      </button>
    </div>
  );
}
