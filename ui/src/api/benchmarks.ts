import type { RagValidationRunResult, WorkflowTraceStep } from "./workflows";

export type BenchmarkSummary = {
  id: string;
  name: string;
  description: string;
  workflow_id: string;
};

export type BenchmarkStage =
  | "indexing"
  | "embedding"
  | "retrieving"
  | "validating"
  | "complete"
  | "error";

export type OptimizationStage =
  | "baseline"
  | "searching"
  | "saving"
  | "after"
  | "complete"
  | "error";

export type BenchmarkProgressEvent = {
  stage: BenchmarkStage;
  progress: number;
  message: string;
  step?: number | null;
  total?: number | null;
  node_id?: string | null;
  scenario_id?: string | null;
  scenario_index?: number | null;
  scenario_total?: number | null;
};

export type DatasetBenchmarkScenarioRow = {
  scenario_name: string;
  query: string;
  phrase_coverage: number;
  first_phrase_rank_reciprocal: number;
  gold_semantic_relevance: number;
  gold_semantic_precision: number;
  validation_passed: boolean;
};

export type DatasetBenchmarkReport = {
  scenario_count?: number;
  mean_phrase_coverage: number;
  mean_first_phrase_rank_reciprocal: number;
  mean_gold_semantic_relevance?: number;
  mean_gold_semantic_precision?: number;
  validation_pass_rate: number;
  hyperparameters: Record<string, string | number | boolean>;
  scenarios: DatasetBenchmarkScenarioRow[];
};

export type OptimizationProgressEvent = {
  stage: OptimizationStage;
  progress: number;
  message: string;
  scenario_count?: number | null;
  combination_index?: number | null;
  combination_total?: number | null;
};

export type OptimizationScenarioRow = {
  scenario_name: string;
  query: string;
  phrase_coverage: number;
  first_phrase_rank_reciprocal: number;
  gold_semantic_relevance: number;
  gold_semantic_precision: number;
  validation_passed: boolean;
};

export type OptimizationPhaseResult = {
  hyperparameters: Record<string, string | number | boolean>;
  mean_phrase_coverage: number;
  mean_first_phrase_rank_reciprocal: number;
  mean_gold_semantic_relevance?: number;
  mean_gold_semantic_precision?: number;
  validation_pass_rate: number;
  scenarios: OptimizationScenarioRow[];
};

export type RagOptimizationReport = {
  created_at: string;
  scenario_count: number;
  before: OptimizationPhaseResult;
  after: OptimizationPhaseResult;
  diff: {
    mean_phrase_coverage_delta: number;
    mean_first_phrase_rank_reciprocal_delta: number;
    mean_gold_semantic_relevance_delta?: number;
    mean_gold_semantic_precision_delta?: number;
    validation_pass_rate_delta: number;
  };
  optimized_at: string;
  objective: string;
};

export type TestDatasetSummary = {
  total_scenarios: number;
  eval_scenarios: number;
  answer_in_corpus_scenarios: number;
  default_max_scenarios: number;
  scenario_ids: string[];
};

export type BenchmarkCompleteEvent = BenchmarkProgressEvent & {
  stage: "complete";
  progress: 100;
  message?: string;
  result: RagValidationRunResult;
  dataset_report?: DatasetBenchmarkReport | null;
};

export type BenchmarkErrorEvent = BenchmarkProgressEvent & {
  stage: "error";
};

export type BenchmarkStreamEvent =
  | BenchmarkProgressEvent
  | BenchmarkCompleteEvent
  | BenchmarkErrorEvent;

export type OptimizationCompleteEvent = OptimizationProgressEvent & {
  stage: "complete";
  progress: 100;
  report: RagOptimizationReport;
  optimized_hyperparameters: Record<string, string | number | boolean>;
};

export type OptimizationErrorEvent = OptimizationProgressEvent & {
  stage: "error";
};

export type OptimizationStreamEvent =
  | OptimizationProgressEvent
  | OptimizationCompleteEvent
  | OptimizationErrorEvent;

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function fetchBenchmarks(): Promise<BenchmarkSummary[]> {
  const response = await fetch(`${API_BASE}/api/benchmarks`);
  if (!response.ok) {
    throw new Error(`Failed to load benchmarks (${response.status})`);
  }
  return response.json() as Promise<BenchmarkSummary[]>;
}

export async function fetchTestDatasetSummary(): Promise<TestDatasetSummary> {
  const response = await fetch(`${API_BASE}/api/benchmarks/rag/test-dataset-summary`);
  if (!response.ok) {
    throw new Error(`Failed to load test dataset summary (${response.status})`);
  }
  return response.json() as Promise<TestDatasetSummary>;
}

export async function fetchOptimizationReport(): Promise<RagOptimizationReport | null> {
  const response = await fetch(`${API_BASE}/api/benchmarks/rag/optimization-report`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Failed to load optimization report (${response.status})`);
  }
  return response.json() as Promise<RagOptimizationReport>;
}

function parseOptimizationSseChunk(buffer: string): {
  events: OptimizationStreamEvent[];
  remainder: string;
} {
  const events: OptimizationStreamEvent[] = [];
  const parts = buffer.split("\n\n");
  const remainder = parts.pop() ?? "";

  for (const part of parts) {
    const line = part
      .split("\n")
      .map((item) => item.trim())
      .find((item) => item.startsWith("data:"));
    if (!line) {
      continue;
    }
    const payload = line.slice(5).trim();
    if (!payload) {
      continue;
    }
    events.push(JSON.parse(payload) as OptimizationStreamEvent);
  }

  return { events, remainder };
}

function parseSseChunk(buffer: string): { events: BenchmarkStreamEvent[]; remainder: string } {
  const events: BenchmarkStreamEvent[] = [];
  const parts = buffer.split("\n\n");
  const remainder = parts.pop() ?? "";

  for (const part of parts) {
    const line = part
      .split("\n")
      .map((item) => item.trim())
      .find((item) => item.startsWith("data:"));
    if (!line) {
      continue;
    }
    const payload = line.slice(5).trim();
    if (!payload) {
      continue;
    }
    events.push(JSON.parse(payload) as BenchmarkStreamEvent);
  }

  return { events, remainder };
}

export type BenchmarkRunCallbacks = {
  onProgress?: (event: BenchmarkProgressEvent) => void;
  onComplete?: (event: BenchmarkCompleteEvent) => void;
  onError?: (event: BenchmarkErrorEvent) => void;
};

export async function runBenchmarkStream(
  benchmarkId: string,
  body: Record<string, string | number | boolean | string[]>,
  callbacks: BenchmarkRunCallbacks = {},
): Promise<BenchmarkCompleteEvent | null> {
  const response = await fetch(`${API_BASE}/api/benchmarks/${benchmarkId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text();
    const errorEvent: BenchmarkErrorEvent = {
      stage: "error",
      progress: 0,
      message: detail || `Benchmark run failed (${response.status})`,
    };
    callbacks.onError?.(errorEvent);
    throw new Error(errorEvent.message);
  }

  if (!response.body) {
    throw new Error("Benchmark stream returned no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completeEvent: BenchmarkCompleteEvent | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.remainder;

    for (const event of parsed.events) {
      if (event.stage === "complete") {
        completeEvent = event as BenchmarkCompleteEvent;
        callbacks.onComplete?.(completeEvent);
        continue;
      }
      if (event.stage === "error") {
        callbacks.onError?.(event as BenchmarkErrorEvent);
        throw new Error(event.message);
      }
      callbacks.onProgress?.(event);
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      if (event.stage === "complete") {
        completeEvent = event as BenchmarkCompleteEvent;
        callbacks.onComplete?.(completeEvent);
      } else if (event.stage === "error") {
        callbacks.onError?.(event as BenchmarkErrorEvent);
        throw new Error(event.message);
      } else {
        callbacks.onProgress?.(event);
      }
    }
  }

  return completeEvent;
}

export type OptimizationRunCallbacks = {
  onProgress?: (event: OptimizationProgressEvent) => void;
  onComplete?: (event: OptimizationCompleteEvent) => void;
  onError?: (event: OptimizationErrorEvent) => void;
};

export async function runRagOptimizationStream(
  body: Record<string, string | number | boolean> = {},
  callbacks: OptimizationRunCallbacks = {},
): Promise<OptimizationCompleteEvent | null> {
  const response = await fetch(`${API_BASE}/api/benchmarks/rag/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text();
    const errorEvent: OptimizationErrorEvent = {
      stage: "error",
      progress: 0,
      message: detail || `Optimization failed (${response.status})`,
    };
    callbacks.onError?.(errorEvent);
    throw new Error(errorEvent.message);
  }

  if (!response.body) {
    throw new Error("Optimization stream returned no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completeEvent: OptimizationCompleteEvent | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseOptimizationSseChunk(buffer);
    buffer = parsed.remainder;

    for (const event of parsed.events) {
      if (event.stage === "complete") {
        completeEvent = event as OptimizationCompleteEvent;
        callbacks.onComplete?.(completeEvent);
        continue;
      }
      if (event.stage === "error") {
        callbacks.onError?.(event as OptimizationErrorEvent);
        throw new Error(event.message);
      }
      callbacks.onProgress?.(event);
    }
  }

  if (buffer.trim()) {
    const parsed = parseOptimizationSseChunk(`${buffer}\n\n`);
    for (const event of parsed.events) {
      if (event.stage === "complete") {
        completeEvent = event as OptimizationCompleteEvent;
        callbacks.onComplete?.(completeEvent);
      } else if (event.stage === "error") {
        callbacks.onError?.(event as OptimizationErrorEvent);
        throw new Error(event.message);
      } else {
        callbacks.onProgress?.(event);
      }
    }
  }

  return completeEvent;
}

export function benchmarkResultToRagRun(
  result: RagValidationRunResult,
): {
  workflowId: string;
  trace: WorkflowTraceStep[];
  ragRun: {
    workflowId: string;
    validationPassed: boolean;
    validationErrors: string[];
    indexedChunkCount: number;
    documentTitle: string;
    documentSource: string;
    expectedPhrases: string[];
    matchedPhrases: string[];
    missingPhrases: string[];
    ragBenchmarks: Record<string, number>;
    ragEvaluationContext: RagValidationRunResult["rag_evaluation_context"];
  };
} {
  return {
    workflowId: "rag-validation",
    trace: result.trace ?? [],
    ragRun: {
      workflowId: "rag-validation",
      validationPassed: result.validation_passed,
      validationErrors: result.validation_errors,
      indexedChunkCount: result.indexed_chunk_count,
      documentTitle: result.document_title,
      documentSource: result.document_source,
      expectedPhrases: result.expected_phrases,
      matchedPhrases: result.matched_phrases,
      missingPhrases: result.missing_phrases,
      ragBenchmarks: result.rag_benchmarks ?? {},
      ragEvaluationContext: result.rag_evaluation_context ?? null,
    },
  };
}
