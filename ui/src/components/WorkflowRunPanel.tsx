import { useState } from "react";

import {
  runWorkflow,
  type ContentGenerationRunResult,
  type WorkflowGraph,
  type WorkflowTraceStep,
} from "../api/workflows";
import type { ContentRunMeta } from "../lib/traceAnalytics";

export type WorkflowRunOutcome = {
  trace: WorkflowTraceStep[];
  runMeta: ContentRunMeta | null;
};

type WorkflowRunPanelProps = {
  workflow: WorkflowGraph;
  onRunComplete: (outcome: WorkflowRunOutcome) => void;
  onError: (message: string | null) => void;
};

function contentRunMeta(result: ContentGenerationRunResult): ContentRunMeta {
  return {
    generationComplete: result.generation_complete,
    lessonRetryCount: result.lesson_retry_count,
    quizRetryCount: result.quiz_retry_count,
    pblRetryCount: result.pbl_retry_count,
  };
}

export function WorkflowRunPanel({ workflow, onRunComplete, onError }: WorkflowRunPanelProps) {
  const [query, setQuery] = useState("fractions");
  const [maxResults, setMaxResults] = useState(5);
  const [maxWebResults, setMaxWebResults] = useState(5);
  const [maxVideoResults, setMaxVideoResults] = useState(3);
  const [topic, setTopic] = useState("fractions");
  const [gradeLevel, setGradeLevel] = useState("6th grade");
  const [running, setRunning] = useState(false);

  async function handleRun() {
    setRunning(true);
    onError(null);
    try {
      const body: Record<string, string | number | boolean> =
        workflow.id === "content-generation"
          ? { topic, grade_level: gradeLevel }
          : workflow.id === "research-article"
            ? {
                query,
                max_web_results: maxWebResults,
                max_video_results: maxVideoResults,
              }
            : workflow.id === "youtube-search"
              ? { query, max_results: maxResults, language: "en", safe_search: true }
              : { query, max_results: maxResults };
      const result = await runWorkflow(workflow.id, body);
      onRunComplete({
        trace: result.trace ?? [],
        runMeta: workflow.id === "content-generation" ? contentRunMeta(result as ContentGenerationRunResult) : null,
      });
    } catch (runError) {
      onRunComplete({ trace: [], runMeta: null });
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
      ) : workflow.id === "research-article" ? (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Max web results
            <input
              type="number"
              min={1}
              max={25}
              value={maxWebResults}
              onChange={(event) => setMaxWebResults(Number(event.target.value))}
            />
          </label>
          <label>
            Max video results
            <input
              type="number"
              min={1}
              max={25}
              value={maxVideoResults}
              onChange={(event) => setMaxVideoResults(Number(event.target.value))}
            />
          </label>
        </div>
      ) : (
        <div className="run-form">
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <label>
            Max results
            <input
              type="number"
              min={1}
              max={25}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
            />
          </label>
        </div>
      )}
      <button type="button" className="run-button" disabled={running} onClick={() => void handleRun()}>
        {running ? "Running…" : "Run and capture trace"}
      </button>
    </div>
  );
}
