import { useCallback, useEffect, useState } from "react";

import { fetchWorkflows, type WorkflowGraph, type WorkflowTraceStep } from "./api/workflows";
import { WorkflowGraphView } from "./components/WorkflowGraphView";
import { WorkflowRunPanel } from "./components/WorkflowRunPanel";
import { WorkflowStepInspector } from "./components/WorkflowStepInspector";
import { WorkflowTraceReplay } from "./components/WorkflowTraceReplay";
import "./App.css";

export default function App() {
  const [workflows, setWorkflows] = useState<WorkflowGraph[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [trace, setTrace] = useState<WorkflowTraceStep[]>([]);
  const [activeStep, setActiveStep] = useState<WorkflowTraceStep | null>(null);
  const [activeNodeAttempts, setActiveNodeAttempts] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchWorkflows();
        if (cancelled) {
          return;
        }
        setWorkflows(data);
        setSelectedId(data[0]?.id ?? null);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedWorkflow = workflows.find((workflow) => workflow.id === selectedId) ?? null;

  const handleActiveStepChange = useCallback(
    (step: WorkflowTraceStep | null, attempts: Record<string, number>) => {
      setActiveStep(step);
      setActiveNodeAttempts(attempts);
    },
    [],
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Local development only</p>
          <h1>LangGraph Workflow Explorer</h1>
          <p className="subtitle">
            Inspect graphs, run workflows, and replay node execution with validation retries.
          </p>
        </div>
        <div className="status-pill">127.0.0.1</div>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <h2>Workflows</h2>
          {loading && <p className="muted">Loading workflows…</p>}
          {error && <p className="error">{error}</p>}
          <ul className="workflow-list">
            {workflows.map((workflow) => (
              <li key={workflow.id}>
                <button
                  type="button"
                  className={workflow.id === selectedId ? "workflow-card active" : "workflow-card"}
                  onClick={() => {
                    setSelectedId(workflow.id);
                    setTrace([]);
                    setActiveStep(null);
                    setActiveNodeAttempts({});
                    setRunError(null);
                  }}
                >
                  <span className="workflow-name">{workflow.name}</span>
                  <span className="workflow-meta">{workflow.framework}</span>
                  <span className="workflow-description">{workflow.description}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="canvas">
          {selectedWorkflow ? (
            <>
              <div className="canvas-header">
                <h2>{selectedWorkflow.name}</h2>
                <p>{selectedWorkflow.description}</p>
              </div>
              <WorkflowRunPanel
                workflow={selectedWorkflow}
                onTrace={setTrace}
                onError={setRunError}
              />
              {runError && <p className="error run-error">{runError}</p>}
              <WorkflowGraphView
                workflow={selectedWorkflow}
                activeStep={activeStep}
                activeNodeAttempts={activeNodeAttempts}
              />
              <WorkflowTraceReplay trace={trace} onActiveStepChange={handleActiveStepChange} />
              <WorkflowStepInspector step={activeStep} />
            </>
          ) : (
            <div className="empty-state">
              <p>No workflow selected.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
