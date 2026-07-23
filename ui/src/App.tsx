import { useCallback, useEffect, useState } from "react";

import { fetchBenchmarks, type BenchmarkSummary } from "./api/benchmarks";
import { fetchWorkflows, type WorkflowGraph, type WorkflowTraceStep } from "./api/workflows";
import { BenchmarkRunPanel } from "./components/BenchmarkRunPanel";
import { WorkflowGraphView } from "./components/WorkflowGraphView";
import { RagBenchmarkDashboard } from "./components/RagBenchmarkDashboard";
import { WorkflowRunPanel, type RagValidationRunMeta, type WorkflowRunOutcome } from "./components/WorkflowRunPanel";
import { WorkflowRunSummary } from "./components/WorkflowRunSummary";
import { WorkflowStepInspector } from "./components/WorkflowStepInspector";
import { WorkflowTraceReplay } from "./components/WorkflowTraceReplay";
import type { ContentRunMeta } from "./lib/traceAnalytics";
import type { RagWorkflowRunMeta } from "./lib/ragBenchmarks";
import "./App.css";

type AppSegment = "workflows" | "benchmarks";

export default function App() {
  const [segment, setSegment] = useState<AppSegment>("workflows");
  const [workflows, setWorkflows] = useState<WorkflowGraph[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkSummary[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [trace, setTrace] = useState<WorkflowTraceStep[]>([]);
  const [runMeta, setRunMeta] = useState<ContentRunMeta | null>(null);
  const [ragValidation, setRagValidation] = useState<RagValidationRunMeta | null>(null);
  const [ragRun, setRagRun] = useState<RagWorkflowRunMeta | null>(null);
  const [activeStep, setActiveStep] = useState<WorkflowTraceStep | null>(null);
  const [activeNodeAttempts, setActiveNodeAttempts] = useState<Record<string, number>>({});

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [workflowData, benchmarkData] = await Promise.all([
          fetchWorkflows(),
          fetchBenchmarks(),
        ]);
        if (cancelled) {
          return;
        }
        setWorkflows(workflowData);
        setBenchmarks(benchmarkData);
        setSelectedWorkflowId(workflowData[0]?.id ?? null);
        setSelectedBenchmarkId(benchmarkData[0]?.id ?? null);
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

  const selectedWorkflow = workflows.find((workflow) => workflow.id === selectedWorkflowId) ?? null;
  const selectedBenchmark =
    benchmarks.find((benchmark) => benchmark.id === selectedBenchmarkId) ?? null;

  const resetRunState = useCallback(() => {
    setTrace([]);
    setRunMeta(null);
    setRagValidation(null);
    setRagRun(null);
    setActiveStep(null);
    setActiveNodeAttempts({});
    setRunError(null);
  }, []);

  const handleWorkflowRunComplete = useCallback((outcome: WorkflowRunOutcome) => {
    setTrace(outcome.trace);
    setRunMeta(outcome.runMeta);
    setRagValidation(outcome.ragValidation);
    setRagRun(outcome.ragRun);
  }, []);

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
            Inspect graphs, run workflows, replay node execution, and run streamed benchmarks.
          </p>
        </div>
        <div className="status-pill">127.0.0.1</div>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <nav className="segment-nav" aria-label="Primary navigation">
            <button
              type="button"
              className={segment === "workflows" ? "segment-nav__button active" : "segment-nav__button"}
              onClick={() => {
                setSegment("workflows");
                resetRunState();
              }}
            >
              Workflows
            </button>
            <button
              type="button"
              className={segment === "benchmarks" ? "segment-nav__button active" : "segment-nav__button"}
              onClick={() => {
                setSegment("benchmarks");
                resetRunState();
              }}
            >
              Benchmarks
            </button>
          </nav>

          {segment === "workflows" ? (
            <>
              <h2>Workflows</h2>
              {loading && <p className="muted">Loading workflows…</p>}
              {error && <p className="error">{error}</p>}
              <ul className="workflow-list">
                {workflows.map((workflow) => (
                  <li key={workflow.id}>
                    <button
                      type="button"
                      className={
                        workflow.id === selectedWorkflowId ? "workflow-card active" : "workflow-card"
                      }
                      onClick={() => {
                        setSelectedWorkflowId(workflow.id);
                        resetRunState();
                      }}
                    >
                      <span className="workflow-name">{workflow.name}</span>
                      <span className="workflow-meta">{workflow.framework}</span>
                      <span className="workflow-description">{workflow.description}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <h2>Benchmarks</h2>
              {loading && <p className="muted">Loading benchmarks…</p>}
              {error && <p className="error">{error}</p>}
              <ul className="workflow-list">
                {benchmarks.map((benchmark) => (
                  <li key={benchmark.id}>
                    <button
                      type="button"
                      className={
                        benchmark.id === selectedBenchmarkId ? "workflow-card active" : "workflow-card"
                      }
                      onClick={() => {
                        setSelectedBenchmarkId(benchmark.id);
                        resetRunState();
                      }}
                    >
                      <span className="workflow-name">{benchmark.name}</span>
                      <span className="workflow-meta">{benchmark.workflow_id}</span>
                      <span className="workflow-description">{benchmark.description}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>

        <section className="canvas">
          {segment === "workflows" ? (
            selectedWorkflow ? (
              <>
                <div className="canvas-header">
                  <h2>{selectedWorkflow.name}</h2>
                  <p>{selectedWorkflow.description}</p>
                </div>
                <WorkflowRunPanel
                  workflow={selectedWorkflow}
                  onRunComplete={handleWorkflowRunComplete}
                  onError={setRunError}
                />
                {runError && <p className="error run-error">{runError}</p>}
                <RagBenchmarkDashboard
                  workflowId={selectedWorkflow.id}
                  trace={trace}
                  ragRun={ragRun}
                />
                <WorkflowRunSummary trace={trace} runMeta={runMeta} ragValidation={ragValidation} />
                <WorkflowGraphView
                  workflow={selectedWorkflow}
                  trace={trace}
                  activeStep={activeStep}
                  activeNodeAttempts={activeNodeAttempts}
                />
                <WorkflowTraceReplay
                  trace={trace}
                  nodeGroups={selectedWorkflow.node_groups ?? []}
                  onActiveStepChange={handleActiveStepChange}
                />
                <WorkflowStepInspector step={activeStep} />
              </>
            ) : (
              <div className="empty-state">
                <p>No workflow selected.</p>
              </div>
            )
          ) : selectedBenchmark ? (
            <>
              <div className="canvas-header">
                <h2>{selectedBenchmark.name}</h2>
                <p>{selectedBenchmark.description}</p>
              </div>
              <BenchmarkRunPanel
                key={selectedBenchmark.id}
                benchmark={selectedBenchmark}
                onError={setRunError}
              />
              {runError && <p className="error run-error">{runError}</p>}
            </>
          ) : (
            <div className="empty-state">
              <p>No benchmark selected.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
