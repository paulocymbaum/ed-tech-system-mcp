import type { DatasetBenchmarkReport } from "../api/benchmarks";

type DatasetBenchmarkResultsPanelProps = {
  report: DatasetBenchmarkReport | null;
};

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatScore(value: number): string {
  return value.toFixed(3);
}

export function DatasetBenchmarkResultsPanel({ report }: DatasetBenchmarkResultsPanelProps) {
  if (!report) {
    return null;
  }

  const scenarios = report.scenarios ?? [];
  const usesSemantic = (report.mean_gold_semantic_relevance ?? 0) > 0;

  return (
    <div className="dataset-benchmark-results">
      <header>
        <h4>Test-dataset benchmark results</h4>
        <p className="muted">
          {report.scenario_count ?? scenarios.length} scenario(s)
          {usesSemantic ? (
            <>
              {" "}
              · mean semantic relevance {formatScore(report.mean_gold_semantic_relevance ?? 0)} ·
              semantic precision {formatPercent(report.mean_gold_semantic_precision ?? 0)}
            </>
          ) : (
            <> · mean phrase coverage {formatPercent(report.mean_phrase_coverage ?? 0)}</>
          )}{" "}
          · validation pass rate {formatPercent(report.validation_pass_rate ?? 0)}
        </p>
      </header>
      <div className="dataset-benchmark-results__table-wrap">
        <table>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Query</th>
              {usesSemantic ? (
                <>
                  <th>Semantic relevance</th>
                  <th>Semantic precision</th>
                </>
              ) : (
                <>
                  <th>Phrase coverage</th>
                  <th>First-phrase rank</th>
                </>
              )}
              <th>Passed</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((row) => (
              <tr key={row.scenario_name}>
                <td>{row.scenario_name}</td>
                <td>{row.query}</td>
                {usesSemantic ? (
                  <>
                    <td>{formatScore(row.gold_semantic_relevance)}</td>
                    <td>{formatPercent(row.gold_semantic_precision)}</td>
                  </>
                ) : (
                  <>
                    <td>{formatPercent(row.phrase_coverage)}</td>
                    <td>{formatPercent(row.first_phrase_rank_reciprocal)}</td>
                  </>
                )}
                <td>{row.validation_passed ? "✓" : "○"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
