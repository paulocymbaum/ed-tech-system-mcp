import { useEffect, useState } from "react";

import { fetchWorkflows, type WorkflowGraph } from "./api/workflows";
import { WorkflowGraphView } from "./components/WorkflowGraphView";
import "./App.css";

export default function App() {
  const [workflows, setWorkflows] = useState<WorkflowGraph[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Local development only</p>
          <h1>LangGraph Workflow Explorer</h1>
          <p className="subtitle">
            Inspect LangChain / LangGraph orchestration graphs served from the MCP application layer.
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
                  onClick={() => setSelectedId(workflow.id)}
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
              <WorkflowGraphView workflow={selectedWorkflow} />
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
