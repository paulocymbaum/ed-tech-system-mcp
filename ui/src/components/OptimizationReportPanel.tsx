import { useEffect, useState } from "react";

import {
  fetchOptimizationReport,
  type RagOptimizationReport,
} from "../api/benchmarks";

type OptimizationReportPanelProps = {
  report: RagOptimizationReport | null;
  loading?: boolean;
  error?: string | null;
};

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatDelta(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function formatScore(value: number): string {
  return value.toFixed(3);
}

function formatScoreDelta(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

export function OptimizationReportPanel({
  report,
  loading = false,
  error = null,
}: OptimizationReportPanelProps) {
  const [mountedReport, setMountedReport] = useState<RagOptimizationReport | null>(report);
  const [loadError, setLoadError] = useState<string | null>(error);

  useEffect(() => {
    setMountedReport(report);
  }, [report]);

  useEffect(() => {
    if (report !== null) {
      return;
    }

    let cancelled = false;
    void fetchOptimizationReport()
      .then((loaded) => {
        if (!cancelled) {
          setMountedReport(loaded);
          setLoadError(null);
        }
      })
      .catch((fetchError) => {
        if (!cancelled) {
          setMountedReport(null);
          setLoadError(
            fetchError instanceof Error ? fetchError.message : "Failed to load optimization report",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [report]);

  if (loading) {
    return (
      <div className="optimization-report-panel">
        <p className="muted">Building optimization report…</p>
      </div>
    );
  }

  if (!mountedReport) {
    return (
      <div className="optimization-report-panel">
        <p className="muted">
          {loadError ?? "No optimization report yet. Run hyperparameter optimization to generate one."}
        </p>
      </div>
    );
  }

  const beforeRows = mountedReport.before.scenarios;
  const afterByName = new Map(
    mountedReport.after.scenarios.map((row) => [row.scenario_name, row]),
  );
  const usesSemantic = (mountedReport.after.mean_gold_semantic_relevance ?? 0) > 0;

  return (
    <div className="optimization-report-panel">
      <header className="optimization-report-panel__header">
        <div>
          <p className="eyebrow">Optimization report</p>
          <h3>Before / after benchmarks</h3>
          <p className="muted">
            {mountedReport.scenario_count} scenario(s) · optimized {mountedReport.optimized_at}
          </p>
        </div>
        <div className="optimization-report-panel__summary">
          {usesSemantic ? (
            <>
              <div>
                <span className="muted">Mean semantic relevance</span>
                <strong>
                  {formatScore(mountedReport.before.mean_gold_semantic_relevance ?? 0)} →{" "}
                  {formatScore(mountedReport.after.mean_gold_semantic_relevance ?? 0)}
                </strong>
                <span className="optimization-report-panel__delta">
                  {formatScoreDelta(mountedReport.diff.mean_gold_semantic_relevance_delta ?? 0)}
                </span>
              </div>
              <div>
                <span className="muted">Semantic precision</span>
                <strong>
                  {formatPercent(mountedReport.before.mean_gold_semantic_precision ?? 0)} →{" "}
                  {formatPercent(mountedReport.after.mean_gold_semantic_precision ?? 0)}
                </strong>
                <span className="optimization-report-panel__delta">
                  {formatDelta(mountedReport.diff.mean_gold_semantic_precision_delta ?? 0)}
                </span>
              </div>
            </>
          ) : (
            <div>
              <span className="muted">Mean phrase coverage</span>
              <strong>
                {formatPercent(mountedReport.before.mean_phrase_coverage)} →{" "}
                {formatPercent(mountedReport.after.mean_phrase_coverage)}
              </strong>
              <span className="optimization-report-panel__delta">
                {formatDelta(mountedReport.diff.mean_phrase_coverage_delta)}
              </span>
            </div>
          )}
          <div>
            <span className="muted">Validation pass rate</span>
            <strong>
              {formatPercent(mountedReport.before.validation_pass_rate)} →{" "}
              {formatPercent(mountedReport.after.validation_pass_rate)}
            </strong>
            <span className="optimization-report-panel__delta">
              {formatDelta(mountedReport.diff.validation_pass_rate_delta)}
            </span>
          </div>
        </div>
      </header>

      <div className="optimization-report-panel__table-wrap">
        <table className="optimization-report-panel__table">
          <thead>
            <tr>
              <th>Scenario</th>
              {usesSemantic ? (
                <>
                  <th>Before relevance</th>
                  <th>After relevance</th>
                  <th>Delta</th>
                </>
              ) : (
                <>
                  <th>Before coverage</th>
                  <th>After coverage</th>
                  <th>Delta</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {beforeRows.map((beforeRow) => {
              const afterRow = afterByName.get(beforeRow.scenario_name);
              if (usesSemantic) {
                const beforeValue = beforeRow.gold_semantic_relevance;
                const afterValue = afterRow?.gold_semantic_relevance ?? 0;
                const delta = afterValue - beforeValue;
                return (
                  <tr key={beforeRow.scenario_name}>
                    <td>
                      <strong>{beforeRow.scenario_name}</strong>
                      <p className="muted optimization-report-panel__query">{beforeRow.query}</p>
                    </td>
                    <td>{formatScore(beforeValue)}</td>
                    <td>{formatScore(afterValue)}</td>
                    <td>{formatScoreDelta(delta)}</td>
                  </tr>
                );
              }
              const beforeCoverage = beforeRow.phrase_coverage;
              const afterCoverage = afterRow?.phrase_coverage ?? 0;
              const delta = afterCoverage - beforeCoverage;
              return (
                <tr key={beforeRow.scenario_name}>
                  <td>
                    <strong>{beforeRow.scenario_name}</strong>
                    <p className="muted optimization-report-panel__query">{beforeRow.query}</p>
                  </td>
                  <td>{formatPercent(beforeCoverage)}</td>
                  <td>{formatPercent(afterCoverage)}</td>
                  <td>{formatDelta(delta)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
