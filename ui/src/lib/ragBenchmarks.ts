import type { WorkflowTraceStep } from "../api/workflows";

export type ScoreKind = "cosine" | "rrf" | "reranker";

export type RagEvaluationContext = {
  retrieval_mode: "vector" | "hybrid";
  retrieve_limit: number;
  rerank_enabled: boolean;
  rerank_top_n: number;
  effective_k: number;
  score_kind: ScoreKind;
  chunk_size?: number | null;
  chunk_overlap?: number | null;
  indexed_chunk_count?: number | null;
  hybrid_fts_active?: boolean;
  rerank_applied?: boolean;
};

export type RagWorkflowRunMeta = {
  workflowId: string;
  ragBenchmarks?: Record<string, number>;
  ragEvaluationContext?: RagEvaluationContext | null;
  validationPassed?: boolean;
  validationErrors?: string[];
  matchedPhrases?: string[];
  missingPhrases?: string[];
  indexedChunkCount?: number;
  documentTitle?: string;
  documentSource?: string;
  expectedPhrases?: string[];
};

export type RagQualityMetrics = {
  phrase_coverage?: number;
  phrase_chunk_rate?: number;
  any_phrase_hit?: number;
  first_phrase_rank_reciprocal?: number;
  expected_phrase_count?: number;
  matched_phrase_count?: number;
  retrieved_chunk_count?: number;
  gold_semantic_relevance?: number;
  mean_gold_semantic_relevance?: number;
  gold_semantic_precision?: number;
  gold_semantic_rank_reciprocal?: number;
};

export type RetrievalProxyMetrics = {
  chunk_count?: number;
  mean_chunk_score?: number;
  max_chunk_score?: number;
  context_length_chars?: number;
  score_kind?: ScoreKind;
  effective_k?: number;
};

export type RagDashboardData = {
  mode: "validation" | "retrieval";
  quality: RagQualityMetrics;
  retrieval: RetrievalProxyMetrics;
  evaluationContext: RagEvaluationContext | null;
  validationPassed?: boolean;
  validationErrors?: string[];
  matchedPhrases?: string[];
  missingPhrases?: string[];
  indexedChunkCount?: number;
  documentTitle?: string;
  documentSource?: string;
  expectedPhrases?: string[];
};

export type MetricDefinition = {
  key: keyof RagQualityMetrics | keyof RetrievalProxyMetrics;
  label: string;
  description: string;
  format: "percent" | "score" | "count" | "chars";
  source: "quality" | "retrieval";
};

export const VALIDATION_METRICS: MetricDefinition[] = [
  {
    key: "gold_semantic_relevance",
    label: "Gold semantic relevance",
    description: "Max cosine similarity between the gold answer and any retrieved chunk embedding",
    format: "score",
    source: "quality",
  },
  {
    key: "gold_semantic_precision",
    label: "Gold semantic precision",
    description: "Share of retrieved chunks whose embeddings exceed the relevance threshold vs gold",
    format: "percent",
    source: "quality",
  },
  {
    key: "mean_gold_semantic_relevance",
    label: "Mean gold semantic relevance",
    description: "Average cosine similarity between the gold answer and retrieved chunk embeddings",
    format: "score",
    source: "quality",
  },
  {
    key: "gold_semantic_rank_reciprocal",
    label: "Semantic rank (1/r)",
    description: "Reciprocal rank of the first chunk semantically relevant to the gold answer",
    format: "percent",
    source: "quality",
  },
  {
    key: "phrase_coverage",
    label: "Phrase coverage",
    description: "Share of expected phrases found as substrings in retrieved chunks",
    format: "percent",
    source: "quality",
  },
  {
    key: "phrase_chunk_rate",
    label: "Phrase-bearing chunk rate",
    description: "Share of retrieved chunks that contain at least one expected phrase",
    format: "percent",
    source: "quality",
  },
  {
    key: "any_phrase_hit",
    label: "Any-phrase hit",
    description: "Binary: 1 when any chunk contains an expected phrase (k = effective chunk count)",
    format: "percent",
    source: "quality",
  },
  {
    key: "first_phrase_rank_reciprocal",
    label: "First-phrase rank (1/r)",
    description: "Reciprocal rank of the first chunk containing any expected phrase",
    format: "percent",
    source: "quality",
  },
];

export const RETRIEVAL_METRICS: MetricDefinition[] = [
  {
    key: "max_chunk_score",
    label: "Max chunk score",
    description: "Highest score among retrieved chunks (semantics depend on score kind)",
    format: "score",
    source: "retrieval",
  },
  {
    key: "mean_chunk_score",
    label: "Mean chunk score",
    description: "Average score across retrieved chunks (semantics depend on score kind)",
    format: "score",
    source: "retrieval",
  },
  {
    key: "chunk_count",
    label: "Chunks retrieved",
    description: "Number of chunks returned by retrieval",
    format: "count",
    source: "retrieval",
  },
  {
    key: "context_length_chars",
    label: "Context size",
    description: "Character length of merged context passed downstream",
    format: "chars",
    source: "retrieval",
  },
];

const SCORE_KIND_LABELS: Record<ScoreKind, string> = {
  cosine: "cosine similarity",
  rrf: "hybrid RRF",
  reranker: "cross-encoder reranker",
};

export function scoreKindLabel(kind: ScoreKind | undefined): string {
  if (!kind) {
    return "unknown";
  }
  return SCORE_KIND_LABELS[kind];
}

function asRecord(value: unknown): Record<string, number> | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const record: Record<string, number> = {};
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "number" && Number.isFinite(item)) {
      record[key] = item;
    }
  }
  return Object.keys(record).length > 0 ? record : null;
}

function asEvaluationContext(value: unknown): RagEvaluationContext | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  const scoreKind = raw.score_kind;
  if (scoreKind !== "cosine" && scoreKind !== "rrf" && scoreKind !== "reranker") {
    return null;
  }
  const retrievalMode = raw.retrieval_mode;
  if (retrievalMode !== "vector" && retrievalMode !== "hybrid") {
    return null;
  }
  return {
    retrieval_mode: retrievalMode,
    retrieve_limit: Number(raw.retrieve_limit),
    rerank_enabled: Boolean(raw.rerank_enabled),
    rerank_top_n: Number(raw.rerank_top_n),
    effective_k: Number(raw.effective_k),
    score_kind: scoreKind,
    chunk_size: typeof raw.chunk_size === "number" ? raw.chunk_size : null,
    chunk_overlap: typeof raw.chunk_overlap === "number" ? raw.chunk_overlap : null,
    indexed_chunk_count:
      typeof raw.indexed_chunk_count === "number" ? raw.indexed_chunk_count : null,
  };
}

function pickMetrics<T extends Record<string, number>>(
  source: Record<string, number> | null | undefined,
  keys: (keyof T)[],
): Partial<T> {
  if (!source) {
    return {};
  }
  const picked: Partial<T> = {};
  for (const key of keys) {
    const value = source[String(key)];
    if (typeof value === "number") {
      picked[key] = value as T[keyof T];
    }
  }
  return picked;
}

export function extractRagBenchmarksFromTrace(trace: WorkflowTraceStep[]): RagQualityMetrics {
  const validateStep = [...trace]
    .reverse()
    .find((step) => step.node_id === "validate_retrieval");
  const fromTrace = asRecord(validateStep?.output_update?.rag_benchmarks);
  return pickMetrics<RagQualityMetrics>(fromTrace, [
    "gold_semantic_relevance",
    "mean_gold_semantic_relevance",
    "gold_semantic_precision",
    "gold_semantic_rank_reciprocal",
    "phrase_coverage",
    "phrase_chunk_rate",
    "any_phrase_hit",
    "first_phrase_rank_reciprocal",
    "expected_phrase_count",
    "matched_phrase_count",
    "retrieved_chunk_count",
  ]);
}

export function extractRetrievalMetricsFromTrace(trace: WorkflowTraceStep[]): RetrievalProxyMetrics {
  const mergeStep = [...trace].reverse().find((step) => step.node_id === "merge_context");
  const fromTrace = asRecord(mergeStep?.output_update?.retrieval_metrics);
  const metrics = pickMetrics<{
    chunk_count?: number;
    mean_chunk_score?: number;
    max_chunk_score?: number;
    context_length_chars?: number;
    effective_k?: number;
  }>(fromTrace, [
    "chunk_count",
    "mean_chunk_score",
    "max_chunk_score",
    "context_length_chars",
    "effective_k",
  ]);
  const scoreKind = mergeStep?.output_update?.retrieval_metrics;
  const rawKind =
    scoreKind && typeof scoreKind === "object" && !Array.isArray(scoreKind)
      ? (scoreKind as Record<string, unknown>).score_kind
      : undefined;
  if (rawKind === "cosine" || rawKind === "rrf" || rawKind === "reranker") {
    return { ...metrics, score_kind: rawKind };
  }
  return metrics;
}

export function extractEvaluationContextFromTrace(
  trace: WorkflowTraceStep[],
): RagEvaluationContext | null {
  const mergeStep = [...trace].reverse().find((step) => step.node_id === "merge_context");
  const fromMerge = asEvaluationContext(mergeStep?.output_update?.rag_evaluation_context);
  if (fromMerge) {
    return fromMerge;
  }
  const validateStep = [...trace]
    .reverse()
    .find((step) => step.node_id === "validate_retrieval");
  return asEvaluationContext(validateStep?.output_update?.rag_evaluation_context);
}

export function hasQualityMetrics(metrics: RagQualityMetrics): boolean {
  return (
    metrics.gold_semantic_relevance !== undefined ||
    metrics.gold_semantic_precision !== undefined ||
    metrics.mean_gold_semantic_relevance !== undefined ||
    metrics.phrase_coverage !== undefined ||
    metrics.phrase_chunk_rate !== undefined ||
    metrics.any_phrase_hit !== undefined ||
    metrics.first_phrase_rank_reciprocal !== undefined
  );
}

export function hasRetrievalMetrics(metrics: RetrievalProxyMetrics): boolean {
  return (
    metrics.chunk_count !== undefined ||
    metrics.mean_chunk_score !== undefined ||
    metrics.max_chunk_score !== undefined ||
    metrics.context_length_chars !== undefined
  );
}

const DEFAULT_SCORE_THRESHOLDS = { good: 0.75, warn: 0.45 };
const RRF_SCORE_THRESHOLDS = { good: 0.02, warn: 0.01 };
const RERANK_SCORE_THRESHOLDS = { good: 0.5, warn: 0.02 };

export function scoreThresholdsForKind(scoreKind: ScoreKind | undefined): {
  good: number;
  warn: number;
} {
  if (scoreKind === "rrf") {
    return RRF_SCORE_THRESHOLDS;
  }
  if (scoreKind === "reranker") {
    return RERANK_SCORE_THRESHOLDS;
  }
  return DEFAULT_SCORE_THRESHOLDS;
}

export function scoreBand(
  value: number,
  format: MetricDefinition["format"],
  scoreKind?: ScoreKind,
): "good" | "warn" | "bad" {
  if (format === "count" || format === "chars") {
    return value > 0 ? "good" : "bad";
  }
  if (format === "score") {
    const thresholds = scoreThresholdsForKind(scoreKind);
    if (value >= thresholds.good) {
      return "good";
    }
    if (value >= thresholds.warn) {
      return "warn";
    }
    return "bad";
  }
  if (value >= 0.8) {
    return "good";
  }
  if (value >= 0.5) {
    return "warn";
  }
  return "bad";
}

export function formatMetricValue(value: number | undefined, format: MetricDefinition["format"]): string {
  if (value === undefined) {
    return "—";
  }
  if (format === "percent") {
    return `${Math.round(value * 100)}%`;
  }
  if (format === "score") {
    return value.toFixed(3);
  }
  if (format === "chars") {
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}k chars`;
    }
    return `${Math.round(value)} chars`;
  }
  return String(Math.round(value));
}

export function primaryValidationScore(metrics: RagQualityMetrics): number | undefined {
  if (metrics.gold_semantic_relevance !== undefined) {
    return metrics.gold_semantic_relevance;
  }
  if (metrics.mean_gold_semantic_relevance !== undefined) {
    return metrics.mean_gold_semantic_relevance;
  }
  return (
    metrics.phrase_coverage ??
    metrics.phrase_chunk_rate ??
    metrics.any_phrase_hit ??
    metrics.first_phrase_rank_reciprocal
  );
}

export function buildRagDashboardData(input: {
  workflowId: string;
  trace: WorkflowTraceStep[];
  ragBenchmarks?: Record<string, number>;
  ragEvaluationContext?: RagEvaluationContext | null;
  validationPassed?: boolean;
  validationErrors?: string[];
  matchedPhrases?: string[];
  missingPhrases?: string[];
  indexedChunkCount?: number;
  documentTitle?: string;
  documentSource?: string;
  expectedPhrases?: string[];
}): RagDashboardData | null {
  const qualityFromApi = pickMetrics<RagQualityMetrics>(input.ragBenchmarks, [
    "gold_semantic_relevance",
    "mean_gold_semantic_relevance",
    "gold_semantic_precision",
    "gold_semantic_rank_reciprocal",
    "phrase_coverage",
    "phrase_chunk_rate",
    "any_phrase_hit",
    "first_phrase_rank_reciprocal",
    "expected_phrase_count",
    "matched_phrase_count",
    "retrieved_chunk_count",
  ]);
  const qualityFromTrace = extractRagBenchmarksFromTrace(input.trace);
  const quality: RagQualityMetrics = { ...qualityFromTrace, ...qualityFromApi };
  const retrieval = extractRetrievalMetricsFromTrace(input.trace);
  const evaluationContext =
    input.ragEvaluationContext ?? extractEvaluationContextFromTrace(input.trace);

  const isValidation = input.workflowId === "rag-validation";
  const isRetrieval = input.workflowId === "rag-retrieval";

  if (!isValidation && !isRetrieval) {
    return null;
  }
  if (!hasQualityMetrics(quality) && !hasRetrievalMetrics(retrieval)) {
    return null;
  }

  return {
    mode: isValidation ? "validation" : "retrieval",
    quality,
    retrieval,
    evaluationContext,
    validationPassed: input.validationPassed,
    validationErrors: input.validationErrors,
    matchedPhrases: input.matchedPhrases,
    missingPhrases: input.missingPhrases,
    indexedChunkCount: input.indexedChunkCount,
    documentTitle: input.documentTitle,
    documentSource: input.documentSource,
    expectedPhrases: input.expectedPhrases,
  };
}
