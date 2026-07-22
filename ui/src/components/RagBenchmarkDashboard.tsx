import type { WorkflowTraceStep } from "../api/workflows";
import type { RagEvaluationContext, RagWorkflowRunMeta } from "../lib/ragBenchmarks";
import {
  RETRIEVAL_METRICS,
  VALIDATION_METRICS,
  buildRagDashboardData,
  formatMetricValue,
  hasQualityMetrics,
  hasRetrievalMetrics,
  primaryValidationScore,
  scoreBand,
  scoreKindLabel,
  scoreThresholdsForKind,
  type MetricDefinition,
  type ScoreKind,
} from "../lib/ragBenchmarks";

export type { RagWorkflowRunMeta } from "../lib/ragBenchmarks";

type RagBenchmarkDashboardProps = {
  workflowId: string | null;
  trace: WorkflowTraceStep[];
  ragRun: RagWorkflowRunMeta | null;
};

function ScoreRing({
  value,
  label,
  subtitle,
  band,
}: {
  value: number | undefined;
  label: string;
  subtitle?: string;
  band: "good" | "warn" | "bad";
}) {
  const pct = value === undefined ? 0 : Math.min(100, Math.max(0, value * 100));
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className={`rag-score-ring rag-score-ring--${band}`}>
      <svg viewBox="0 0 128 128" aria-hidden="true">
        <circle className="rag-score-ring__track" cx="64" cy="64" r={radius} />
        <circle
          className="rag-score-ring__progress"
          cx="64"
          cy="64"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="rag-score-ring__content">
        <span className="rag-score-ring__value">{value === undefined ? "—" : `${Math.round(pct)}%`}</span>
        <span className="rag-score-ring__label">{label}</span>
        {subtitle ? <span className="rag-score-ring__subtitle">{subtitle}</span> : null}
      </div>
    </div>
  );
}

function MetricBar({
  metric,
  value,
  scoreKind,
}: {
  metric: MetricDefinition;
  value: number | undefined;
  scoreKind?: ScoreKind;
}) {
  const band = value === undefined ? "warn" : scoreBand(value, metric.format, scoreKind);
  const width =
    value === undefined
      ? 0
      : metric.format === "percent" || metric.format === "score"
        ? Math.min(100, Math.max(0, value * 100))
        : metric.format === "chars"
          ? Math.min(100, (value / 8000) * 100)
          : Math.min(100, value * 10);

  return (
    <article className={`rag-metric-card rag-metric-card--${band}`}>
      <div className="rag-metric-card__header">
        <h4>{metric.label}</h4>
        <span className="rag-metric-card__value">{formatMetricValue(value, metric.format)}</span>
      </div>
      <div className="rag-metric-card__bar" aria-hidden="true">
        <span className="rag-metric-card__bar-fill" style={{ width: `${width}%` }} />
      </div>
      <p className="rag-metric-card__description">{metric.description}</p>
    </article>
  );
}

function RunContextBanner({ context }: { context: RagEvaluationContext }) {
  const thresholds = scoreThresholdsForKind(context.score_kind);
  return (
    <div className="rag-context-banner">
      <h4>Run context</h4>
      <dl className="rag-context-banner__grid">
        <div>
          <dt>Retrieval mode</dt>
          <dd>{context.retrieval_mode}</dd>
        </div>
        <div>
          <dt>Retrieve limit</dt>
          <dd>{context.retrieve_limit}</dd>
        </div>
        <div>
          <dt>Rerank</dt>
          <dd>{context.rerank_enabled ? `on (top ${context.rerank_top_n})` : "off"}</dd>
        </div>
        <div>
          <dt>Effective k</dt>
          <dd>{context.effective_k}</dd>
        </div>
        <div>
          <dt>Score kind</dt>
          <dd>{scoreKindLabel(context.score_kind)}</dd>
        </div>
        {context.chunk_size != null && (
          <div>
            <dt>Chunk size / overlap</dt>
            <dd>
              {context.chunk_size} / {context.chunk_overlap ?? "—"}
            </dd>
          </div>
        )}
        {context.indexed_chunk_count != null && (
          <div>
            <dt>Indexed chunks</dt>
            <dd>{context.indexed_chunk_count}</dd>
          </div>
        )}
      </dl>
      {context.score_kind !== "cosine" && (
        <p className="rag-context-banner__thresholds">
          Score thresholds ({scoreKindLabel(context.score_kind)}): good ≥ {thresholds.good}, warn ≥
          {thresholds.warn}
        </p>
      )}
    </div>
  );
}

function PhraseChips({
  phrases,
  matchedPhrases,
  missingPhrases,
}: {
  phrases: string[];
  matchedPhrases?: string[];
  missingPhrases?: string[];
}) {
  if (phrases.length === 0) {
    return null;
  }

  const matchedSet = new Set(matchedPhrases ?? []);
  const missingSet = new Set(missingPhrases ?? []);

  function isPhraseMatched(phrase: string): boolean {
    if (matchedSet.size > 0 || missingSet.size > 0) {
      return matchedSet.has(phrase);
    }
    return true;
  }

  return (
    <div className="rag-phrase-chips">
      <h4>Expected phrases</h4>
      <ul>
        {phrases.map((phrase) => {
          const matched = isPhraseMatched(phrase);
          return (
            <li key={phrase} className={matched ? "rag-phrase-chip rag-phrase-chip--matched" : "rag-phrase-chip"}>
              <span className="rag-phrase-chip__icon" aria-hidden="true">
                {matched ? "✓" : "○"}
              </span>
              {phrase}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function RagBenchmarkDashboard({ workflowId, trace, ragRun }: RagBenchmarkDashboardProps) {
  if (!workflowId || !ragRun || trace.length === 0) {
    return null;
  }

  const data = buildRagDashboardData({
    workflowId,
    trace,
    ragBenchmarks: ragRun.ragBenchmarks,
    ragEvaluationContext: ragRun.ragEvaluationContext,
    validationPassed: ragRun.validationPassed,
    validationErrors: ragRun.validationErrors,
    matchedPhrases: ragRun.matchedPhrases,
    missingPhrases: ragRun.missingPhrases,
    indexedChunkCount: ragRun.indexedChunkCount,
    documentTitle: ragRun.documentTitle,
    documentSource: ragRun.documentSource,
    expectedPhrases: ragRun.expectedPhrases,
  });

  if (!data) {
    return null;
  }

  const showValidation = data.mode === "validation" && hasQualityMetrics(data.quality);
  const showRetrieval = hasRetrievalMetrics(data.retrieval);
  const scoreKind =
    data.evaluationContext?.score_kind ?? data.retrieval.score_kind ?? "cosine";
  const heroScore = showValidation ? primaryValidationScore(data.quality) : undefined;
  const heroBand = heroScore === undefined ? "warn" : scoreBand(heroScore, "percent");
  const heroLabel = showValidation ? "Phrase coverage" : "Retrieval diagnostics";
  const heroSubtitle =
    showValidation && data.quality.expected_phrase_count !== undefined
      ? `${data.quality.matched_phrase_count ?? 0}/${data.quality.expected_phrase_count} phrases matched`
      : data.retrieval.chunk_count !== undefined
        ? `${data.retrieval.chunk_count} chunks · ${scoreKindLabel(scoreKind)}`
        : undefined;

  const statusLabel =
    data.mode === "validation"
      ? data.validationPassed
        ? "Smoke test passed"
        : "Smoke test failed"
      : "Retrieval complete";

  const statusBand =
    data.mode === "validation" ? (data.validationPassed ? "good" : "bad") : "good";

  return (
    <section className="rag-dashboard" aria-labelledby="rag-dashboard-title">
      <header className="rag-dashboard__header">
        <div>
          <p className="rag-dashboard__eyebrow">
            {data.mode === "validation" ? "Pipeline smoke test" : "Retrieval diagnostics"}
          </p>
          <h3 id="rag-dashboard-title">
            {data.mode === "validation" ? "RAG pipeline smoke test" : "RAG retrieval diagnostics"}
          </h3>
          <p className="rag-dashboard__subtitle">
            {data.mode === "validation"
              ? "Closed-loop check: indexes the same document it queries. Measures pipeline wiring, not production corpus quality."
              : "Retrieval-only proxies from the latest run — no ground-truth phrases."}
          </p>
        </div>
        <span className={`rag-dashboard__status rag-dashboard__status--${statusBand}`}>{statusLabel}</span>
      </header>

      {data.evaluationContext && <RunContextBanner context={data.evaluationContext} />}

      <div className="rag-dashboard__hero">
        {showValidation ? (
          <ScoreRing value={heroScore} label={heroLabel} subtitle={heroSubtitle} band={heroBand} />
        ) : (
          <div className="rag-dashboard__hero-stats">
            <h4>{heroLabel}</h4>
            <p className="rag-dashboard__hero-stat-value">{heroSubtitle ?? "—"}</p>
            {data.retrieval.max_chunk_score !== undefined && (
              <p className="rag-dashboard__hero-stat-detail">
                Max score ({scoreKindLabel(scoreKind)}):{" "}
                {formatMetricValue(data.retrieval.max_chunk_score, "score")}
              </p>
            )}
          </div>
        )}
        <div className="rag-dashboard__hero-meta">
          <dl>
            {data.mode === "validation" && (
              <>
                <div>
                  <dt>Document</dt>
                  <dd>
                    {data.documentTitle || "—"}
                    {data.documentSource ? ` (${data.documentSource})` : ""}
                  </dd>
                </div>
                <div>
                  <dt>Indexed chunks</dt>
                  <dd>{data.indexedChunkCount ?? "—"}</dd>
                </div>
                <div>
                  <dt>Retrieved chunks</dt>
                  <dd>{data.quality.retrieved_chunk_count ?? data.retrieval.chunk_count ?? "—"}</dd>
                </div>
              </>
            )}
            {data.mode === "retrieval" && (
              <>
                <div>
                  <dt>Chunks retrieved</dt>
                  <dd>{data.retrieval.chunk_count ?? "—"}</dd>
                </div>
                <div>
                  <dt>Context size</dt>
                  <dd>{formatMetricValue(data.retrieval.context_length_chars, "chars")}</dd>
                </div>
                <div>
                  <dt>Mean score</dt>
                  <dd>{formatMetricValue(data.retrieval.mean_chunk_score, "score")}</dd>
                </div>
              </>
            )}
          </dl>
          {data.validationErrors && data.validationErrors.length > 0 && (
            <p className="rag-dashboard__alert">{data.validationErrors.join(" · ")}</p>
          )}
        </div>
      </div>

      {showValidation && (
        <div className="rag-dashboard__section">
          <h4>Phrase smoke test metrics</h4>
          <div className="rag-dashboard__grid">
            {VALIDATION_METRICS.map((metric) => (
              <MetricBar
                key={metric.key}
                metric={metric}
                value={data.quality[metric.key as keyof typeof data.quality]}
              />
            ))}
          </div>
        </div>
      )}

      {showRetrieval && (
        <div className="rag-dashboard__section">
          <h4>Retrieval diagnostics</h4>
          <div className="rag-dashboard__grid">
            {RETRIEVAL_METRICS.map((metric) => (
              <MetricBar
                key={metric.key}
                metric={metric}
                value={data.retrieval[metric.key as keyof typeof data.retrieval]}
                scoreKind={metric.format === "score" ? scoreKind : undefined}
              />
            ))}
          </div>
        </div>
      )}

      {data.mode === "validation" && data.expectedPhrases && data.expectedPhrases.length > 0 && (
        <PhraseChips
          phrases={data.expectedPhrases}
          matchedPhrases={data.matchedPhrases}
          missingPhrases={data.missingPhrases}
        />
      )}
    </section>
  );
}
