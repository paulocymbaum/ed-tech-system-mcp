import { useEffect, useState } from "react";

import {
  benchmarkResultToRagRun,
  fetchTestDatasetSummary,
  runBenchmarkStream,
  runRagOptimizationStream,
  type BenchmarkProgressEvent,
  type BenchmarkSummary,
  type DatasetBenchmarkReport,
  type OptimizationProgressEvent,
  type RagOptimizationReport,
  type TestDatasetSummary,
} from "../api/benchmarks";
import type { WorkflowTraceStep } from "../api/workflows";
import type { RagWorkflowRunMeta } from "../lib/ragBenchmarks";
import { BenchmarkProgressBar } from "./BenchmarkProgressBar";
import { DatasetBenchmarkResultsPanel } from "./DatasetBenchmarkResultsPanel";
import { OptimizationReportPanel } from "./OptimizationReportPanel";
import { RagBenchmarkDashboard } from "./RagBenchmarkDashboard";

type BenchmarkRunPanelProps = {
  benchmark: BenchmarkSummary;
  onError: (message: string | null) => void;
};

export function BenchmarkRunPanel({ benchmark, onError }: BenchmarkRunPanelProps) {
  const [retrieveLimit, setRetrieveLimit] = useState(4);
  const [rerankTopN, setRerankTopN] = useState(4);
  const [rerankEnabled, setRerankEnabled] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<"vector" | "hybrid">("vector");
  const [maxScenarios, setMaxScenarios] = useState(12);
  const [running, setRunning] = useState(false);
  const [progressEvent, setProgressEvent] = useState<BenchmarkProgressEvent | null>(null);
  const [localTrace, setLocalTrace] = useState<WorkflowTraceStep[]>([]);
  const [localRagRun, setLocalRagRun] = useState<RagWorkflowRunMeta | null>(null);
  const [datasetReport, setDatasetReport] = useState<DatasetBenchmarkReport | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [datasetSummary, setDatasetSummary] = useState<TestDatasetSummary | null>(null);
  const [datasetSummaryError, setDatasetSummaryError] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizationProgress, setOptimizationProgress] = useState<OptimizationProgressEvent | null>(
    null,
  );
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [optimizationReport, setOptimizationReport] = useState<RagOptimizationReport | null>(null);

  useEffect(() => {
    if (benchmark.id !== "rag") {
      return;
    }

    let cancelled = false;
    void fetchTestDatasetSummary()
      .then((summary) => {
        if (!cancelled) {
          setDatasetSummary(summary);
          setMaxScenarios(summary.default_max_scenarios);
          setDatasetSummaryError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDatasetSummary(null);
          setDatasetSummaryError(
            error instanceof Error ? error.message : "Failed to load test-dataset summary",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [benchmark.id]);

  function hyperparameterBody(): Record<string, string | number | boolean> {
    return {
      retrieval_mode: retrievalMode,
      retrieve_limit: retrieveLimit,
      rerank_top_n: rerankTopN,
      rerank_enabled: rerankEnabled,
      max_scenarios: maxScenarios,
    };
  }

  async function handleRun() {
    setRunning(true);
    setStreamError(null);
    onError(null);
    setProgressEvent({
      stage: "indexing",
      progress: 0,
      message: "Starting test-dataset benchmark…",
    });
    setLocalTrace([]);
    setLocalRagRun(null);
    setDatasetReport(null);

    try {
      const completeEvent = await runBenchmarkStream(benchmark.id, hyperparameterBody(), {
        onProgress: (event) => {
          setProgressEvent(event);
        },
      });

      if (!completeEvent) {
        throw new Error("Benchmark finished without a complete event");
      }

      const outcome = benchmarkResultToRagRun(completeEvent.result);
      setProgressEvent({
        stage: "complete",
        progress: 100,
        message: completeEvent.message ?? "Benchmark complete",
      });
      setLocalTrace(outcome.trace);
      setLocalRagRun(outcome.ragRun);
      setDatasetReport(completeEvent.dataset_report ?? null);
    } catch (runError) {
      const message = runError instanceof Error ? runError.message : "Benchmark run failed";
      setStreamError(message);
      setProgressEvent((current) =>
        current
          ? { ...current, stage: "error", message }
          : { stage: "error", progress: 0, message },
      );
      onError(message);
    } finally {
      setRunning(false);
    }
  }

  async function handleOptimize() {
    setOptimizing(true);
    setOptimizationError(null);
    onError(null);
    setOptimizationProgress({
      stage: "baseline",
      progress: 0,
      message: "Starting hyperparameter optimization…",
      scenario_count: maxScenarios,
    });

    try {
      const completeEvent = await runRagOptimizationStream(hyperparameterBody(), {
        onProgress: (event) => {
          setOptimizationProgress(event);
        },
      });

      if (!completeEvent) {
        throw new Error("Optimization finished without a complete event");
      }

      setOptimizationProgress({
        stage: "complete",
        progress: 100,
        message: "Hyperparameter optimization complete",
      });
      setOptimizationReport(completeEvent.report);

      const optimized = completeEvent.optimized_hyperparameters;
      if (typeof optimized.retrieve_limit === "number") {
        setRetrieveLimit(optimized.retrieve_limit);
      }
      if (typeof optimized.rerank_top_n === "number") {
        setRerankTopN(optimized.rerank_top_n);
      }
      if (typeof optimized.rerank_enabled === "boolean") {
        setRerankEnabled(optimized.rerank_enabled);
      }
      if (optimized.retrieval_mode === "vector" || optimized.retrieval_mode === "hybrid") {
        setRetrievalMode(optimized.retrieval_mode);
      }
    } catch (optimizeError) {
      const message =
        optimizeError instanceof Error ? optimizeError.message : "Hyperparameter optimization failed";
      setOptimizationError(message);
      setOptimizationProgress((current) =>
        current
          ? { ...current, stage: "error", message }
          : { stage: "error", progress: 0, message },
      );
      onError(message);
    } finally {
      setOptimizing(false);
    }
  }

  return (
    <div className="benchmark-run-panel">
      <header className="benchmark-run-panel__header">
        <div>
          <p className="eyebrow">Benchmark</p>
          <h3>{benchmark.name}</h3>
          <p className="muted">{benchmark.description}</p>
        </div>
      </header>

      {benchmark.id === "rag" && (
        <div className="run-form run-form--document">
          <p className="muted run-form-note">
            Runs <strong>rag-validation</strong> once per scenario from <code>test-dataset/</code>{" "}
            (not the photosynthesis fixture). Each scenario indexes its own document and evaluates phrase
            coverage.
          </p>
          {datasetSummary ? (
            <div className="dataset-scenario-list">
              <p className="muted run-form-note">
                {datasetSummary.answer_in_corpus_scenarios} eval scenarios with answers in corpus.
                Running up to <strong>{maxScenarios}</strong> per benchmark/optimization pass.
              </p>
              <ul className="dataset-scenario-list__items">
                {datasetSummary.scenario_ids.map((scenarioId) => (
                  <li key={scenarioId}>{scenarioId}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="run-form-note run-form-note--warn">
              {datasetSummaryError ??
                "test-dataset/ not available — place the CSV bundle at the repo root to run benchmarks."}
            </p>
          )}
          <label>
            Max scenarios per run
            <input
              type="number"
              min={1}
              max={datasetSummary?.answer_in_corpus_scenarios ?? 100}
              value={maxScenarios}
              onChange={(event) => setMaxScenarios(Number(event.target.value))}
            />
          </label>
          <label>
            Retrieval mode
            <select
              value={retrievalMode}
              onChange={(event) => setRetrievalMode(event.target.value as "vector" | "hybrid")}
            >
              <option value="vector">vector</option>
              <option value="hybrid">hybrid</option>
            </select>
          </label>
          <label>
            Retrieve limit
            <input
              type="number"
              min={1}
              max={100}
              value={retrieveLimit}
              onChange={(event) => setRetrieveLimit(Number(event.target.value))}
            />
          </label>
          <label>
            Rerank top n
            <input
              type="number"
              min={1}
              max={50}
              value={rerankTopN}
              disabled={!rerankEnabled}
              onChange={(event) => setRerankTopN(Number(event.target.value))}
            />
          </label>
          <label className="run-form-checkbox">
            <input
              type="checkbox"
              checked={rerankEnabled}
              onChange={(event) => setRerankEnabled(event.target.checked)}
            />
            Enable rerank
          </label>
        </div>
      )}

      <button
        type="button"
        className="run-button"
        disabled={running || optimizing || (benchmark.id === "rag" && !datasetSummary)}
        onClick={() => void handleRun()}
      >
        {running ? "Running benchmark…" : "Run test-dataset benchmark"}
      </button>

      {benchmark.id === "rag" && (
        <div className="benchmark-run-panel__optimize">
          <p className="muted run-form-note">
            Optimization captures a before snapshot with the hyperparameters above, grid-searches all
            combinations, saves <code>optimized_hyperparameters.json</code>, then runs an after snapshot
            and writes <code>optimization_report.json</code>.
          </p>
          <button
            type="button"
            className="run-button run-button--secondary"
            disabled={optimizing || running || !datasetSummary}
            onClick={() => void handleOptimize()}
          >
            {optimizing ? "Optimizing hyperparameters…" : "Optimize hyperparameters"}
          </button>
          {optimizationProgress && (
            <BenchmarkProgressBar
              progress={optimizationProgress.progress}
              stage={optimizationProgress.stage}
              message={optimizationProgress.message}
              running={optimizing}
              error={optimizationError}
            />
          )}
          <OptimizationReportPanel
            report={optimizationReport}
            loading={optimizing}
            error={optimizationError}
          />
        </div>
      )}

      {progressEvent && (
        <BenchmarkProgressBar
          progress={progressEvent.progress}
          stage={progressEvent.stage}
          message={progressEvent.message}
          running={running}
          error={streamError}
        />
      )}

      <DatasetBenchmarkResultsPanel report={datasetReport} />

      <RagBenchmarkDashboard
        workflowId={benchmark.workflow_id}
        trace={localTrace}
        ragRun={localRagRun}
      />
    </div>
  );
}
