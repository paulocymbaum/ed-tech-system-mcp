import type { ContentRunMeta } from "../lib/traceAnalytics";
import { summarizeTrace, totalRetryCount, type TraceSummary } from "../lib/traceAnalytics";
import type { WorkflowTraceStep } from "../api/workflows";
import type { RagValidationRunMeta } from "./WorkflowRunPanel";

type WorkflowRunSummaryProps = {
  trace: WorkflowTraceStep[];
  runMeta: ContentRunMeta | null;
  ragValidation: RagValidationRunMeta | null;
};

function formatNodeId(nodeId: string | null) {
  if (!nodeId) {
    return "—";
  }
  return nodeId.replaceAll("_", " ");
}

export function WorkflowRunSummary({ trace, runMeta, ragValidation }: WorkflowRunSummaryProps) {
  if (trace.length === 0) {
    return null;
  }

  const summary: TraceSummary = summarizeTrace(trace);
  const apiRetries = runMeta ? totalRetryCount(runMeta) : 0;
  const incomplete = runMeta?.generationComplete === false;
  const validationFailed = ragValidation?.validationPassed === false;
  const cleanRun = !summary.hasIssues && apiRetries === 0 && !incomplete && !validationFailed;

  return (
    <div className={`run-summary ${cleanRun ? "run-summary--ok" : "run-summary--warn"}`}>
      <div className="run-summary__header">
        <h3>Run summary</h3>
        <span className={`run-summary__badge ${cleanRun ? "run-summary__badge--ok" : "run-summary__badge--warn"}`}>
          {cleanRun ? "completed cleanly" : "issues detected"}
        </span>
      </div>

      <dl className="run-summary__stats">
        <div>
          <dt>Steps recorded</dt>
          <dd>{summary.totalSteps}</dd>
        </div>
        <div>
          <dt>Failed steps</dt>
          <dd className={summary.failedSteps > 0 ? "run-summary__highlight-failed" : undefined}>
            {summary.failedSteps}
          </dd>
        </div>
        <div>
          <dt>Retry decisions</dt>
          <dd className={summary.retrySteps > 0 ? "run-summary__highlight-retry" : undefined}>
            {summary.retrySteps}
          </dd>
        </div>
        <div>
          <dt>Last node</dt>
          <dd>{formatNodeId(summary.lastNodeId)}</dd>
        </div>
      </dl>

      {runMeta && (
        <p className="run-summary__meta">
          Validation retries · lesson: {runMeta.lessonRetryCount ?? 0} · quiz: {runMeta.quizRetryCount ?? 0} ·
          pbl: {runMeta.pblRetryCount ?? 0}
          {runMeta.generationComplete !== undefined && (
            <> · generation complete: {runMeta.generationComplete ? "yes" : "no"}</>
          )}
        </p>
      )}

      {validationFailed && (
        <p className="run-summary__alert">
          Validation failed: {ragValidation.validationErrors.join(" · ")}
        </p>
      )}

      {incomplete && (
        <p className="run-summary__alert">
          Workflow finished without reaching merge results. Artifacts may be partial even if earlier steps look
          successful.
        </p>
      )}

      {summary.hasIssues && (
        <p className="run-summary__hint muted">
          Failed and retry steps are highlighted below. Use Prev/Next or click a step to inspect validation errors
          and LLM I/O.
        </p>
      )}
    </div>
  );
}
